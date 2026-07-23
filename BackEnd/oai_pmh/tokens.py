"""Opaque resumption tokens for OAI-PMH paged responses.

Tokens carry just enough state that the harvester can request the next page
without the server maintaining session storage. Encoded as
base64url(json({...})) so they survive URL round-trips without escaping.
"""
import base64
import json
from typing import Optional


class BadToken(Exception):
    pass


def encode(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode(token: str) -> dict:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        obj = json.loads(raw.decode("utf-8"))
        if not isinstance(obj, dict):
            raise BadToken("token payload is not an object")
        return obj
    except Exception as exc:  # noqa: BLE001
        raise BadToken(str(exc)) from exc


def build(
    *,
    verb: str,
    metadata_prefix: str,
    cursor: int,
    page_size: int,
    set_spec: Optional[str] = None,
    frm: Optional[str] = None,
    until: Optional[str] = None,
) -> str:
    payload = {
        "v": verb,
        "m": metadata_prefix,
        "c": cursor,
        "p": page_size,
    }
    if set_spec:
        payload["s"] = set_spec
    if frm:
        payload["f"] = frm
    if until:
        payload["u"] = until
    return encode(payload)


def parse(token: str) -> dict:
    obj = decode(token)
    if "v" not in obj or "m" not in obj or "c" not in obj or "p" not in obj:
        raise BadToken("token missing required keys")
    return {
        "verb": obj["v"],
        "metadata_prefix": obj["m"],
        "cursor": int(obj["c"]),
        "page_size": int(obj["p"]),
        "set_spec": obj.get("s"),
        "frm": obj.get("f"),
        "until": obj.get("u"),
    }
