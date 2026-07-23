"""Adapters that turn Article / GreyLiterature rows into the Dublin Core
payload OAI-PMH templates render. Also owns identifier + set spec syntax.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, Optional

from django.conf import settings

from journalApis.models import Article, Journal


IDENTIFIER_NAMESPACE = "afrikajournals.org"

# DCMI type vocabulary mapping for grey-literature subtypes
_GREY_TYPE_TO_DCMI = {
    "policy_brief": "Text",
    "working_paper": "Text",
    "technical_report": "Text",
    "evaluation_report": "Text",
    "thesis": "Text",
    "dissertation": "Text",
    "conference_proceedings": "Text",
    "government_report": "Text",
    "blog": "Text",
    "newsletter": "Text",
    "dataset": "Dataset",
    "other": "Text",
}

_SENTINEL_EARLIEST = "2020-01-01T00:00:00Z"


def _site_url() -> str:
    return getattr(settings, "SITE_URL", "https://afrikajournals.org").rstrip("/")


def _iso_utc(dt) -> str:
    if dt is None:
        return _SENTINEL_EARLIEST
    if hasattr(dt, "hour"):
        d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{dt.isoformat()}T00:00:00Z"


def _split_multi(value: Optional[str]) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[;,\n]+", value)
    return [p.strip() for p in parts if p and p.strip()]


# ---------------------------------------------------------------------------
# Identifiers

def article_identifier(article_id: int) -> str:
    return f"oai:{IDENTIFIER_NAMESPACE}:article/{article_id}"


def grey_identifier(grey_id: int) -> str:
    return f"oai:{IDENTIFIER_NAMESPACE}:grey/{grey_id}"


_IDENT_RE = re.compile(rf"^oai:{re.escape(IDENTIFIER_NAMESPACE)}:(article|grey)/(\d+)$")


def parse_identifier(identifier: str) -> tuple[str, int]:
    """Return (kind, id) or raise ValueError."""
    m = _IDENT_RE.match(identifier or "")
    if not m:
        raise ValueError(f"malformed OAI identifier: {identifier!r}")
    return m.group(1), int(m.group(2))


# ---------------------------------------------------------------------------
# Sets

JOURNAL_SET_PREFIX = "journal:"
GREY_ROOT_SET = "grey"
GREY_SUBTYPE_PREFIX = "grey:"


def article_set_specs(article) -> list[str]:
    if article.journal_id and article.journal and getattr(article.journal, "slug", None):
        return [f"{JOURNAL_SET_PREFIX}{article.journal.slug}"]
    return []


def grey_set_specs(item) -> list[str]:
    specs = [GREY_ROOT_SET]
    if item.item_type:
        specs.append(f"{GREY_SUBTYPE_PREFIX}{item.item_type}")
    return specs


# ---------------------------------------------------------------------------
# Datestamps

def article_datestamp(article) -> str:
    return _iso_utc(getattr(article, "updated_at", None) or article.publication_date)


def grey_datestamp(item) -> str:
    return _iso_utc(item.updated_at or item.publication_date)


def earliest_datestamp() -> str:
    from grey_literature.models import GreyLiterature

    candidates = []
    art_min = (
        Article.objects.filter(journal__approved=True)
        .exclude(updated_at__isnull=True)
        .order_by("updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )
    grey_min = (
        GreyLiterature.objects.filter(approved=True)
        .exclude(updated_at__isnull=True)
        .order_by("updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )
    for c in (art_min, grey_min):
        if c is not None:
            candidates.append(c)
    if not candidates:
        return _SENTINEL_EARLIEST
    return _iso_utc(min(candidates))


# ---------------------------------------------------------------------------
# Dublin Core payload builders

def _article_landing_url(article) -> str:
    slug = getattr(article.journal, "slug", None) if article.journal_id else None
    if slug:
        return f"{_site_url()}/journals/{slug}/articles/{article.id}/"
    return f"{_site_url()}/journal_api/api/article/{article.id}/"


def _grey_landing_url(item) -> str:
    return f"{_site_url()}/grey/{item.slug}/"


def _article_source(article) -> Optional[str]:
    parts = []
    if article.journal_id and article.journal:
        parts.append(article.journal.journal_title)
    if article.volume_id and article.volume:
        parts.append(f"Vol. {article.volume.volume_number}")
        if article.volume.issue_number:
            parts.append(f"Issue {article.volume.issue_number}")
    if article.page_start and article.page_end:
        parts.append(f"pp. {article.page_start}-{article.page_end}")
    elif article.page_start:
        parts.append(f"p. {article.page_start}")
    return ", ".join(parts) if parts else None


def article_dc(article) -> dict:
    identifiers = [_article_landing_url(article)]
    if article.doi:
        identifiers.append(f"info:doi:{article.doi.strip()}")
    if article.pdf:
        try:
            identifiers.append(f"{_site_url()}{article.pdf.url}")
        except Exception:
            pass
    return {
        "title": article.title or "",
        "creators": _split_multi(article.authors),
        "subjects": _split_multi(article.keywords),
        "description": article.abstract or "",
        "publisher": article.journal.journal_title if (article.journal_id and article.journal) else "",
        "date": article.publication_date.isoformat() if article.publication_date else "",
        "type": "Text",
        "format": "application/pdf" if article.pdf else "",
        "identifiers": identifiers,
        "source": _article_source(article) or "",
        "language": (article.language or "").strip(),
        "coverage": "",
        "rights": (article.license_url or "").strip(),
    }


def grey_dc(item) -> dict:
    identifiers = [_grey_landing_url(item)]
    if item.doi:
        identifiers.append(f"info:doi:{item.doi.strip()}")
    if item.file:
        try:
            identifiers.append(f"{_site_url()}{item.file.url}")
        except Exception:
            pass
    coverage_parts = []
    if item.country_id and item.country:
        coverage_parts.append(item.country.country)
    if item.sub_region:
        coverage_parts.append(item.sub_region)
    return {
        "title": item.title or "",
        "creators": _split_multi(item.authors),
        "subjects": _split_multi(item.keywords),
        "description": item.abstract or "",
        "publisher": item.issuing_organization or "",
        "date": item.publication_date.isoformat() if item.publication_date else "",
        "type": _GREY_TYPE_TO_DCMI.get(item.item_type, "Text"),
        "format": "application/pdf" if item.file else "",
        "identifiers": identifiers,
        "source": item.source or "",
        "language": (item.language or "").strip(),
        "coverage": "; ".join(coverage_parts),
        "rights": "",
    }


# ---------------------------------------------------------------------------
# Query helpers used by verb handlers

def base_article_queryset():
    return (
        Article.objects.select_related("journal", "volume")
        .filter(journal__approved=True)
    )


def base_grey_queryset():
    from grey_literature.models import GreyLiterature

    return GreyLiterature.objects.select_related("country").filter(approved=True)


def all_journal_sets() -> list[dict]:
    return [
        {"spec": f"{JOURNAL_SET_PREFIX}{j.slug}", "name": j.journal_title}
        for j in Journal.objects.filter(approved=True)
        .exclude(slug__isnull=True)
        .exclude(slug="")
        .only("slug", "journal_title")
        .order_by("journal_title")
    ]


def all_grey_type_sets() -> list[dict]:
    from grey_literature.models import GREY_LIT_TYPES, GreyLiterature

    used = set(
        GreyLiterature.objects.filter(approved=True)
        .values_list("item_type", flat=True)
        .distinct()
    )
    label_map = dict(GREY_LIT_TYPES)
    return [
        {"spec": f"{GREY_SUBTYPE_PREFIX}{code}", "name": f"Grey Literature: {label_map.get(code, code)}"}
        for code in sorted(used)
    ]


def all_sets() -> Iterable[dict]:
    yield from all_journal_sets()
    yield {"spec": GREY_ROOT_SET, "name": "Grey Literature (all types)"}
    yield from all_grey_type_sets()


def resolve_set(set_spec: Optional[str]) -> tuple[Iterable, Optional[str]]:
    """Return (iterator-of-records, error_code_or_None). Records are tagged
    with `_kind` so the caller knows how to build headers/metadata.
    """
    if set_spec is None:
        return _merged_iterator(base_article_queryset(), base_grey_queryset()), None
    if set_spec == GREY_ROOT_SET:
        return _tagged_iterator("grey", base_grey_queryset()), None
    if set_spec.startswith(GREY_SUBTYPE_PREFIX):
        subtype = set_spec[len(GREY_SUBTYPE_PREFIX):]
        qs = base_grey_queryset().filter(item_type=subtype)
        return _tagged_iterator("grey", qs), None
    if set_spec.startswith(JOURNAL_SET_PREFIX):
        slug = set_spec[len(JOURNAL_SET_PREFIX):]
        if not Journal.objects.filter(slug=slug, approved=True).exists():
            return iter([]), "noRecordsMatch"
        qs = base_article_queryset().filter(journal__slug=slug)
        return _tagged_iterator("article", qs), None
    return iter([]), "noRecordsMatch"


def _tagged_iterator(kind, qs):
    for obj in qs.iterator(chunk_size=200):
        obj._kind = kind  # noqa: SLF001
        yield obj


def _merged_iterator(art_qs, grey_qs):
    # OAI-PMH sort by datestamp isn't strictly required but harvesters expect
    # a stable order. We emit articles first (by id), then grey lit (by id).
    for a in art_qs.order_by("id").iterator(chunk_size=200):
        a._kind = "article"  # noqa: SLF001
        yield a
    for g in grey_qs.order_by("id").iterator(chunk_size=200):
        g._kind = "grey"  # noqa: SLF001
        yield g


def build_record_context(obj) -> dict:
    """Given an object tagged with _kind, produce the context dict the
    templates expect.
    """
    if obj._kind == "article":  # noqa: SLF001
        return {
            "identifier": article_identifier(obj.id),
            "datestamp": article_datestamp(obj),
            "sets": article_set_specs(obj),
            "dc": article_dc(obj),
        }
    return {
        "identifier": grey_identifier(obj.id),
        "datestamp": grey_datestamp(obj),
        "sets": grey_set_specs(obj),
        "dc": grey_dc(obj),
    }


def lookup(identifier: str):
    kind, pk = parse_identifier(identifier)
    if kind == "article":
        obj = base_article_queryset().filter(pk=pk).first()
    else:
        obj = base_grey_queryset().filter(pk=pk).first()
    if obj is None:
        return None
    obj._kind = kind  # noqa: SLF001
    return obj
