"""Merge whitespace/case duplicate rows in Language / Country / Platform /
ThematicArea, repoint every Journal + GreyLiterature FK to the canonical
row, then delete the losers.

Runs inside a single transaction. --dry-run to preview.

Normalization: casefold + collapse-whitespace + strip. So 'English' and
'English ' collapse together; 'sciElo' and 'SciELO' collapse together;
'African\xa0Index\xa0Medicus (AIM)' (non-breaking spaces) collapses with the
regular-space form. It does NOT collapse comma-adjacent whitespace, so
'English, Afrikaans' and 'English,Afrikaans' stay separate.

Canonical picker (per dupe group):
  1. Prefer rows whose raw value equals its stripped form (no leading/trailing
     whitespace and no non-breaking spaces). Cleanest presentation.
  2. Among those, prefer the row with the most Journal FKs pointing to it
     (fewer rows to repoint).
  3. Break tie: lowest id (oldest row).

After picking, the canonical row's field is updated to the cleaned form
(strip + collapse-whitespace, preserving the winner's case).
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from django.core.management.base import BaseCommand
from django.db import transaction

from journalApis.models import (
    Journal, Language, Country, Platform, ThematicArea,
)

try:
    from grey_literature.models import GreyLiterature
except Exception:
    GreyLiterature = None


_WS = re.compile(r"\s+")


def normalize(s: str | None) -> str:
    if not s:
        return ""
    return _WS.sub(" ", s).strip().casefold()


def clean(s: str) -> str:
    """The value we write back to the canonical row: whitespace-normalized,
    but case preserved (we're merging into an existing spelling, not
    canonicalizing case)."""
    return _WS.sub(" ", s).strip()


# (model, field_name_on_model, journal-fk field name, grey-fk field name or None,
#  m2m-through-attr-on-Journal or None)
TAXONOMIES = [
    (Language, "language", "language", None, "languages"),
    (Country, "country", "country", "country", None),
    (Platform, "platform", "platform", None, None),
    (ThematicArea, "thematic_area", "thematic_area", None, "disciplines"),
]


class Command(BaseCommand):
    help = "Merge whitespace/case duplicate Language/Country/Platform/ThematicArea rows."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview without writing.")

    def handle(self, *args, dry_run: bool = False, **opts):
        summary = []
        with transaction.atomic():
            for model, field, journal_fk, grey_fk, m2m_attr in TAXONOMIES:
                stats = self._dedup_model(model, field, journal_fk, grey_fk, m2m_attr, dry_run)
                summary.append((model.__name__, stats))
            if dry_run:
                self.stdout.write(self.style.WARNING("\n--- DRY RUN: rolling back ---"))
                transaction.set_rollback(True)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Summary"))
        for name, s in summary:
            self.stdout.write(
                f"  {name}: {s['before']} -> {s['after']} rows "
                f"(merged {s['merged_groups']} groups, "
                f"repointed {s['journal_updates']} Journal FKs, "
                f"{s['m2m_updates']} M2M rows, "
                f"{s['grey_updates']} GreyLiterature FKs, "
                f"deleted {s['deleted']} rows)"
            )

    def _dedup_model(self, model, field, journal_fk, grey_fk, m2m_attr, dry_run):
        rows = list(model.objects.all().order_by("id"))
        groups = defaultdict(list)
        for r in rows:
            groups[normalize(getattr(r, field))].append(r)
        dupe_groups = [(k, v) for k, v in groups.items() if len(v) > 1]

        stats = {
            "before": len(rows),
            "after": len(rows),
            "merged_groups": 0,
            "journal_updates": 0,
            "m2m_updates": 0,
            "grey_updates": 0,
            "deleted": 0,
        }

        for norm_key, group_rows in dupe_groups:
            canonical = self._pick_canonical(group_rows, field, journal_fk)
            losers: Iterable = [r for r in group_rows if r.id != canonical.id]
            desired_value = clean(getattr(canonical, field))

            self.stdout.write(
                f"[{model.__name__}] group {norm_key!r}: canonical=[{canonical.id}] {getattr(canonical, field)!r} "
                f"-> keep as {desired_value!r}"
            )

            # 1. Update canonical's field to clean form if it differs
            if getattr(canonical, field) != desired_value:
                setattr(canonical, field, desired_value)
                canonical.save(update_fields=[field])

            for dup in losers:
                # Journal FK
                n = Journal.objects.filter(**{journal_fk: dup}).update(**{journal_fk: canonical.id})
                stats["journal_updates"] += n

                # M2M through table
                if m2m_attr:
                    m2m = getattr(Journal, m2m_attr).through
                    remote_col = self._m2m_remote_column(m2m, model)
                    # Delete rows where the same journal already has the canonical to avoid unique-constraint clash
                    existing_pairs = set(m2m.objects.filter(**{remote_col: canonical.id}).values_list("journal_id", flat=True))
                    if existing_pairs:
                        m2m.objects.filter(**{remote_col: dup.id}, journal_id__in=existing_pairs).delete()
                    n = m2m.objects.filter(**{remote_col: dup.id}).update(**{remote_col: canonical.id})
                    stats["m2m_updates"] += n

                # GreyLiterature FK
                if grey_fk and GreyLiterature is not None:
                    n = GreyLiterature.objects.filter(**{grey_fk: dup}).update(**{grey_fk: canonical.id})
                    stats["grey_updates"] += n

                self.stdout.write(f"    merged [{dup.id}] {getattr(dup, field)!r} -> [{canonical.id}]")
                dup.delete()
                stats["deleted"] += 1

            stats["merged_groups"] += 1

        stats["after"] = model.objects.count()
        return stats

    def _pick_canonical(self, rows, field, journal_fk):
        # 1. clean-value rows first
        def sort_key(r):
            raw = getattr(r, field) or ""
            is_clean = raw == clean(raw)
            journal_count = Journal.objects.filter(**{journal_fk: r}).count()
            # negate journal_count so higher counts sort first (asc order)
            return (0 if is_clean else 1, -journal_count, r.id)
        return sorted(rows, key=sort_key)[0]

    def _m2m_remote_column(self, m2m_model, remote_model):
        for f in m2m_model._meta.get_fields():
            if getattr(f, "related_model", None) is remote_model:
                return f"{f.name}_id"
        raise RuntimeError(f"could not find FK from {m2m_model} to {remote_model}")
