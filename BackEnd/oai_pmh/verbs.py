"""Verb handlers. Each returns (template_name, context_dict) or raises
OaiError to render the error envelope.
"""
from __future__ import annotations

import itertools
from typing import Optional

from django.conf import settings

from . import records, tokens


PAGE_SIZE = 100
SUPPORTED_METADATA_PREFIX = "oai_dc"


class OaiError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------

def _admin_email() -> str:
    admins = getattr(settings, "ADMINS", None) or []
    if admins:
        return admins[0][1]
    return getattr(settings, "DEFAULT_FROM_EMAIL", "admin@afrikajournals.org")


def _repository_name() -> str:
    return getattr(settings, "OAI_REPOSITORY_NAME", "African Journals Platform")


def _base_url(request) -> str:
    site = getattr(settings, "SITE_URL", None)
    if site:
        return f"{site.rstrip('/')}/oai"
    return request.build_absolute_uri(request.path)


# ---------------------------------------------------------------------------
# Argument validation helpers

_ALLOWED_ARGS = {
    "Identify": {"verb"},
    "ListMetadataFormats": {"verb", "identifier"},
    "ListSets": {"verb", "resumptionToken"},
    "ListIdentifiers": {"verb", "from", "until", "set", "metadataPrefix", "resumptionToken"},
    "ListRecords": {"verb", "from", "until", "set", "metadataPrefix", "resumptionToken"},
    "GetRecord": {"verb", "identifier", "metadataPrefix"},
}


def _validate_args(verb: str, params: dict):
    allowed = _ALLOWED_ARGS.get(verb)
    if allowed is None:
        raise OaiError("badVerb", f"Unknown verb: {verb!r}")
    unknown = set(params.keys()) - allowed
    if unknown:
        raise OaiError("badArgument", f"Illegal argument(s): {', '.join(sorted(unknown))}")


def _reject_extra_with_resumption(params: dict, extra_keys: set):
    if "resumptionToken" in params:
        conflicting = extra_keys & set(params.keys())
        if conflicting:
            raise OaiError(
                "badArgument",
                "resumptionToken must be the only argument besides verb",
            )


# ---------------------------------------------------------------------------
# Verb: Identify

def identify(request, params):
    _validate_args("Identify", params)
    return "oai_pmh/identify.xml", {
        "repository_name": _repository_name(),
        "base_url": _base_url(request),
        "admin_email": _admin_email(),
        "earliest_datestamp": records.earliest_datestamp(),
    }


# ---------------------------------------------------------------------------
# Verb: ListMetadataFormats

def list_metadata_formats(request, params):
    _validate_args("ListMetadataFormats", params)
    identifier = params.get("identifier")
    if identifier is not None:
        obj = records.lookup(identifier)
        if obj is None:
            raise OaiError("idDoesNotExist", identifier)
    return "oai_pmh/list_metadata_formats.xml", {}


# ---------------------------------------------------------------------------
# Verb: ListSets

def list_sets(request, params):
    _validate_args("ListSets", params)
    if "resumptionToken" in params:
        raise OaiError("badResumptionToken", "ListSets does not paginate in this repository")
    return "oai_pmh/list_sets.xml", {"sets": list(records.all_sets())}


# ---------------------------------------------------------------------------
# Verbs: ListIdentifiers / ListRecords

def _paged_list(
    request, params, template_name: str, verb_name: str
):
    _validate_args(verb_name, params)
    _reject_extra_with_resumption(params, {"from", "until", "set", "metadataPrefix"})

    if "resumptionToken" in params:
        try:
            state = tokens.parse(params["resumptionToken"])
        except tokens.BadToken:
            raise OaiError("badResumptionToken", "Malformed or expired resumption token")
        if state["verb"] != verb_name:
            raise OaiError("badResumptionToken", "Token verb mismatch")
        metadata_prefix = state["metadata_prefix"]
        cursor = state["cursor"]
        page_size = state["page_size"]
        set_spec = state["set_spec"]
        frm = state["frm"]
        until = state["until"]
    else:
        metadata_prefix = params.get("metadataPrefix")
        if not metadata_prefix:
            raise OaiError("badArgument", "metadataPrefix is required")
        cursor = 0
        page_size = PAGE_SIZE
        set_spec = params.get("set")
        frm = params.get("from")
        until = params.get("until")

    if metadata_prefix != SUPPORTED_METADATA_PREFIX:
        raise OaiError("cannotDisseminateFormat", metadata_prefix)

    iterator, err = records.resolve_set(set_spec)
    if err:
        raise OaiError(err)

    filtered = _apply_date_filter(iterator, frm, until)
    # advance to cursor
    for _ in itertools.islice(filtered, cursor):
        pass
    page = list(itertools.islice(filtered, page_size))
    if not page and cursor == 0:
        raise OaiError("noRecordsMatch")

    # is there another page?
    has_more = next(filtered, None) is not None
    next_token = None
    if has_more:
        next_token = tokens.build(
            verb=verb_name,
            metadata_prefix=metadata_prefix,
            cursor=cursor + page_size,
            page_size=page_size,
            set_spec=set_spec,
            frm=frm,
            until=until,
        )

    record_contexts = [records.build_record_context(o) for o in page]
    return template_name, {
        "records": record_contexts,
        "resumption_token": next_token,
        "cursor": cursor,
    }


def list_identifiers(request, params):
    return _paged_list(request, params, "oai_pmh/list_identifiers.xml", "ListIdentifiers")


def list_records(request, params):
    return _paged_list(request, params, "oai_pmh/list_records.xml", "ListRecords")


# ---------------------------------------------------------------------------
# Verb: GetRecord

def get_record(request, params):
    _validate_args("GetRecord", params)
    identifier = params.get("identifier")
    metadata_prefix = params.get("metadataPrefix")
    if not identifier or not metadata_prefix:
        raise OaiError("badArgument", "identifier and metadataPrefix are required")
    if metadata_prefix != SUPPORTED_METADATA_PREFIX:
        raise OaiError("cannotDisseminateFormat", metadata_prefix)
    try:
        obj = records.lookup(identifier)
    except ValueError:
        raise OaiError("idDoesNotExist", identifier)
    if obj is None:
        raise OaiError("idDoesNotExist", identifier)
    return "oai_pmh/get_record.xml", {"record": records.build_record_context(obj)}


# ---------------------------------------------------------------------------
# Date filtering (from / until)

def _parse_utc_date(value: Optional[str]):
    if not value:
        return None
    # OAI-PMH accepts YYYY-MM-DD or YYYY-MM-DDThh:mm:ssZ
    return value.strip()


def _apply_date_filter(iterator, frm, until):
    frm = _parse_utc_date(frm)
    until = _parse_utc_date(until)
    if not (frm or until):
        yield from iterator
        return
    for obj in iterator:
        ds = obj._kind == "article" and records.article_datestamp(obj) or records.grey_datestamp(obj)  # noqa: SLF001
        if frm and ds < frm:
            continue
        if until and ds > until:
            continue
        yield obj


VERB_HANDLERS = {
    "Identify": identify,
    "ListMetadataFormats": list_metadata_formats,
    "ListSets": list_sets,
    "ListIdentifiers": list_identifiers,
    "ListRecords": list_records,
    "GetRecord": get_record,
}
