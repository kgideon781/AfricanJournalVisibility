"""Backfill Journal.issn_number for catalogue journals by asking CrossRef what
journal each orphan article's ISSN belongs to, then fuzzy-matching the
returned title against our catalogue.

Motivation: our AJOL/SABINET import populated 2005 journals but only 337 of
them have an ISSN filled in. The 14,753 CrossRef-imported articles carry
ISSNs but couldn't be linked because their parent journals in the catalogue
lack ISSN metadata. This command closes that gap.

Flow:
    unique orphan ISSNs → CrossRef `/journals/{issn}` → canonical title →
    fuzzy match against Journal.journal_title (only journals without ISSN) →
    if match ≥ threshold, backfill Journal.issn_number.

After running this, re-run `manage.py link_articles_by_issn` to link the
now-newly-matchable articles.

Usage:
    python manage.py backfill_journal_issns --dry-run
    python manage.py backfill_journal_issns --threshold 0.9
    python manage.py backfill_journal_issns                 # write
"""
import difflib
import json
import re
import time
from pathlib import Path

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from journalApis.models import Article, Journal


CROSSREF_ENDPOINT = 'https://api.crossref.org/journals/{issn}'
# CrossRef's "polite pool" — including a mailto in User-Agent gets us
# priority-routed and lets them contact us if we misbehave. Not a secret.
USER_AGENT = 'AJV/1.0 (mailto:gchirchir@aphrc.org)'
CACHE_PATH = Path('/tmp/crossref_issn_cache.json')
DEFAULT_THRESHOLD = 0.85


def _normalize_title(s):
    """Lowercase, drop punctuation, collapse whitespace. Only for comparison —
    the original title is preserved on the model."""
    if not s:
        return ''
    s = s.lower()
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _normalize_issn(raw):
    """Return canonical 'XXXX-YYYY' or None."""
    if not raw:
        return None
    c = ''.join(ch for ch in str(raw).upper() if ch.isdigit() or ch in '-X')
    c = c.strip('-')
    stripped = c.replace('-', '')
    if len(stripped) != 8:
        return None
    return f'{stripped[:4]}-{stripped[4:]}'


class Command(BaseCommand):
    help = (
        'Fetch CrossRef metadata for ISSNs on orphan articles and backfill '
        'Journal.issn_number by fuzzy title match.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--threshold',
            type=float,
            default=DEFAULT_THRESHOLD,
            help='Fuzzy-match ratio threshold [0.0-1.0]. Default 0.85.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Only query the first N unique ISSNs (for testing).',
        )
        parser.add_argument(
            '--rate-sleep',
            type=float,
            default=0.1,
            help='Seconds to sleep between CrossRef calls (polite pool).',
        )
        parser.add_argument(
            '--cache-file',
            default=str(CACHE_PATH),
            help='On-disk JSON cache path for CrossRef responses.',
        )

    def handle(self, *args, dry_run, threshold, limit, rate_sleep, cache_file, **_):
        cache_path = Path(cache_file)
        cache = {}
        if cache_path.exists():
            try:
                cache = json.loads(cache_path.read_text())
                self.stdout.write(f'Loaded cache: {len(cache)} entries from {cache_path}')
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f'Ignoring corrupt cache at {cache_path}: {e}'
                ))
                cache = {}

        # ─── Collect unique orphan ISSNs ────────────────────────────────────
        issns = set()
        for e, p in Article.objects.filter(journal__isnull=True).values_list(
            'electronic_issn', 'print_issn'
        ):
            for v in (e, p):
                n = _normalize_issn(v)
                if n:
                    issns.add(n)
        self.stdout.write(f'Unique orphan ISSNs to resolve: {len(issns)}')

        issns_list = sorted(issns)
        if limit:
            issns_list = issns_list[:limit]
            self.stdout.write(f'Limited to first {len(issns_list)} ISSNs.')

        # ─── Fetch missing entries from CrossRef ────────────────────────────
        session = requests.Session()
        session.headers.update({'User-Agent': USER_AGENT})
        newly_fetched = 0
        errors = 0
        for i, issn in enumerate(issns_list, 1):
            if issn in cache:
                continue
            url = CROSSREF_ENDPOINT.format(issn=issn)
            try:
                resp = session.get(url, timeout=10)
                if resp.status_code == 200:
                    m = resp.json().get('message', {})
                    cache[issn] = {
                        'title': m.get('title'),
                        'publisher': m.get('publisher'),
                        'ISSN': m.get('ISSN', []),
                    }
                else:
                    cache[issn] = {'_status': resp.status_code}
                    if resp.status_code != 404:
                        errors += 1
            except requests.RequestException as exc:
                cache[issn] = {'_error': str(exc)[:200]}
                errors += 1
            newly_fetched += 1
            if i % 50 == 0:
                cache_path.write_text(json.dumps(cache))
                self.stdout.write(f'  fetched {i}/{len(issns_list)}, errors={errors}')
            time.sleep(rate_sleep)
        cache_path.write_text(json.dumps(cache))
        self.stdout.write(
            f'Cache now: {len(cache)} entries. Newly fetched: {newly_fetched}, errors: {errors}'
        )

        # ─── Load journals without ISSN, pre-normalize titles ───────────────
        journals_target = list(
            Journal.objects
            .filter(issn_number__isnull=True)
            .only('id', 'journal_title')
        )
        journals_empty = list(
            Journal.objects
            .filter(issn_number='')
            .only('id', 'journal_title')
        )
        seen = set()
        candidates = []
        for j in journals_target + journals_empty:
            if j.id in seen:
                continue
            seen.add(j.id)
            candidates.append((j, _normalize_title(j.journal_title or '')))
        self.stdout.write(f'Journals without ISSN: {len(candidates)}')

        # ─── Fuzzy match ────────────────────────────────────────────────────
        # For each CrossRef title, find best-matching journal above threshold.
        # Keep the best proposal per journal (a journal might match multiple
        # queried ISSNs if it has both print and online).
        proposals = []  # (ratio, journal, issn, crossref_title)
        for issn in issns_list:
            entry = cache.get(issn) or {}
            cr_title = entry.get('title')
            if not cr_title:
                continue
            cr_norm = _normalize_title(cr_title)
            if not cr_norm:
                continue
            best = None
            for j, jnorm in candidates:
                if not jnorm:
                    continue
                r = difflib.SequenceMatcher(None, cr_norm, jnorm).ratio()
                if r >= threshold and (best is None or r > best[0]):
                    best = (r, j, cr_title)
            if best:
                proposals.append((best[0], best[1], issn, best[2]))

        # One journal → keep the highest-ratio proposal.
        proposals.sort(key=lambda x: -x[0])
        by_journal = {}
        for r, j, issn, cr_title in proposals:
            by_journal.setdefault(j.id, (r, j, issn, cr_title))
        final = list(by_journal.values())
        final.sort(key=lambda x: -x[0])

        self.stdout.write('')
        self.stdout.write(f'PROPOSALS: {len(final)} journals to backfill')
        if final:
            self.stdout.write('  Top 10:')
            for r, j, issn, cr_title in final[:10]:
                self.stdout.write(
                    f'    {r:.2f}  #{j.id}  {issn}  '
                    f'cr={cr_title!r} vs local={j.journal_title!r}'
                )
            self.stdout.write('  Bottom 10 (near threshold — spot check):')
            for r, j, issn, cr_title in final[-10:]:
                self.stdout.write(
                    f'    {r:.2f}  #{j.id}  {issn}  '
                    f'cr={cr_title!r} vs local={j.journal_title!r}'
                )

        if dry_run:
            self.stdout.write(self.style.WARNING('(dry run — no writes)'))
            return

        with transaction.atomic():
            for r, j, issn, cr_title in final:
                Journal.objects.filter(id=j.id).update(issn_number=issn)
        self.stdout.write(self.style.SUCCESS(f'Backfilled {len(final)} journals.'))
