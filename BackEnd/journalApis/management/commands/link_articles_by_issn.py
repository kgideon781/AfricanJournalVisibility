"""Link orphan articles (journal FK = NULL) to journals by ISSN match.

The imported CrossRef article batch carries `electronic_issn` and `print_issn`
strings but was never linked to `Journal` rows. This command builds an
ISSN → Journal lookup and connects the two.

Design notes:
- ISSN normalization: uppercase 'X' (valid checksum char), keep digits + hyphen
  + 'X'. So "2663-4627", "26634627", "2663-4627 " all normalize to "2663-4627"
  (or "26634627" if the hyphen wasn't there — see below).
- Some journals may list multiple ISSNs (print + online); we split on common
  separators (`,` `;` `/`).
- If two journals share the same ISSN — unusual but possible in imported data
  — we drop that ISSN from the lookup rather than picking one arbitrarily.
- Only writes when there's exactly one match. Ambiguous / no-match articles
  stay orphaned (they show up in the counts so we can investigate later).

Usage:
    python manage.py link_articles_by_issn --dry-run       # see numbers, no writes
    python manage.py link_articles_by_issn                 # write for real
    python manage.py link_articles_by_issn --limit 100     # small batch first
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from journalApis.models import Article, Journal


def _normalize_issn(raw):
    """Return a normalized ISSN or None. Both '2663-4627' and '26634627' are
    valid ISSN forms — we keep the hyphen if it's there but also produce a
    hyphen-less variant so lookups match either form."""
    if not raw:
        return None
    cleaned = ''.join(ch for ch in str(raw).upper() if ch.isdigit() or ch in '-X')
    cleaned = cleaned.strip('-')
    if len(cleaned.replace('-', '')) != 8:
        return None
    return cleaned


def _normalize_issn_variants(raw):
    """Return every likely-canonical form of the ISSN so lookups hit even when
    one side has a hyphen and the other doesn't."""
    n = _normalize_issn(raw)
    if not n:
        return set()
    without = n.replace('-', '')
    with_hyphen = f'{without[:4]}-{without[4:]}'
    return {n, without, with_hyphen}


class Command(BaseCommand):
    help = 'Link orphan articles (no journal FK) to journals by ISSN match.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report counts without modifying any rows.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Only process the first N orphan articles.',
        )

    def handle(self, *args, dry_run=False, limit=None, **kwargs):
        # ─── Build ISSN → Journal.id lookup ──────────────────────────────────
        issn_to_journal = {}
        ambiguous = set()
        j_with_issn = 0
        for j in Journal.objects.exclude(issn_number__isnull=True).exclude(
            issn_number=''
        ).only('id', 'issn_number'):
            raw = str(j.issn_number)
            # Split on common separators — a single journal might list both a
            # print and an online ISSN in one column.
            for sep in (',', ';', '/', '\n', ' '):
                raw = raw.replace(sep, '|')
            candidates = [c for c in raw.split('|') if c.strip()]
            if not candidates:
                continue
            j_with_issn += 1
            for c in candidates:
                for variant in _normalize_issn_variants(c):
                    if variant in issn_to_journal and issn_to_journal[variant] != j.id:
                        ambiguous.add(variant)
                    else:
                        issn_to_journal.setdefault(variant, j.id)
        for a in ambiguous:
            issn_to_journal.pop(a, None)

        self.stdout.write(
            f'Journals with an ISSN field:        {j_with_issn}'
        )
        self.stdout.write(
            f'Unique ISSN lookup keys (any form): {len(issn_to_journal)}'
        )
        self.stdout.write(
            f'Ambiguous ISSNs excluded:           {len(ambiguous)}'
        )

        # ─── Walk orphan articles ────────────────────────────────────────────
        orphans_qs = Article.objects.filter(journal__isnull=True).only(
            'id', 'electronic_issn', 'print_issn'
        )
        total_orphans = orphans_qs.count()
        self.stdout.write(f'Orphan articles to consider:        {total_orphans}')

        if limit:
            orphans_qs = orphans_qs.order_by('id')[:limit]

        matched_ids = []  # list of (article_id, journal_id) pairs to write
        no_issn = 0
        no_match = 0

        for a in orphans_qs.iterator(chunk_size=500):
            candidates = []
            for src in (a.electronic_issn, a.print_issn):
                candidates.extend(_normalize_issn_variants(src))

            if not candidates:
                no_issn += 1
                continue

            hit = None
            for c in candidates:
                if c in issn_to_journal:
                    hit = issn_to_journal[c]
                    break

            if hit:
                matched_ids.append((a.id, hit))
            else:
                no_match += 1

        self.stdout.write('')
        self.stdout.write(f'RESULT — matched:                    {len(matched_ids)}')
        self.stdout.write(f'RESULT — no ISSN on article:         {no_issn}')
        self.stdout.write(f'RESULT — no matching journal ISSN:   {no_match}')

        if dry_run:
            self.stdout.write(self.style.WARNING('(dry run — no changes written)'))
            return

        # ─── Write in bulk, in chunks ────────────────────────────────────────
        chunk = 1000
        written = 0
        with transaction.atomic():
            # Group by target journal so we can do bulk updates per journal.
            by_journal = {}
            for a_id, j_id in matched_ids:
                by_journal.setdefault(j_id, []).append(a_id)
            for j_id, ids in by_journal.items():
                for i in range(0, len(ids), chunk):
                    slice_ids = ids[i:i + chunk]
                    Article.objects.filter(id__in=slice_ids).update(
                        journal_id=j_id
                    )
                    written += len(slice_ids)
        self.stdout.write(self.style.SUCCESS(f'Wrote {written} article.journal links.'))
