"""Media serving with per-user signed URLs for sensitive subdirs.

In production (DEBUG=False) Django's default static() helper is a no-op, so
/media/<path> requests 404. This module replaces it with an explicit view
that:

  - serves everything under MEDIA_ROOT publicly EXCEPT paths matching
    _SENSITIVE_PREFIXES (currently just 'manuscripts/');
  - for sensitive paths, requires a valid signed ?token=... query parameter
    that was minted for the same path by make_signed_media_url().

The signer uses SECRET_KEY + TimestampSigner, so tokens are self-contained
(no DB read on hot path) and expire after MEDIA_TOKEN_MAX_AGE seconds.
Serializers that emit sensitive media URLs must wrap them via
make_signed_media_url(request, path).
"""
from __future__ import annotations

import os
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.http import FileResponse, Http404, HttpResponse
from django.utils._os import safe_join

_SIGNER = TimestampSigner(salt="ajv-media-v1")
_MAX_AGE = 30 * 60  # 30 minutes
_SENSITIVE_PREFIXES = ("manuscripts/",)


def _is_sensitive(media_path: str) -> bool:
    return media_path.startswith(_SENSITIVE_PREFIXES)


def make_signed_media_url(request, file_field) -> str:
    """Return an absolute-path (same-origin) signed URL for a FileField.

    Callers pass the FieldFile / ImageFieldFile (or a string path).
    Returns empty string if there is no file.
    """
    if not file_field:
        return ""
    # accept FieldFile or str
    url = getattr(file_field, "url", None) or str(file_field)
    if not url:
        return ""
    # strip MEDIA_URL prefix to get the raw media_path
    rel = url
    if rel.startswith(settings.MEDIA_URL):
        rel = rel[len(settings.MEDIA_URL):]
    rel = rel.lstrip("/")
    if not _is_sensitive(rel):
        # non-sensitive: return the plain URL (no token needed)
        return url
    user_id = 0
    if request is not None and getattr(request, "user", None) and request.user.is_authenticated:
        user_id = request.user.id
    token = _SIGNER.sign(f"{user_id}:{rel}")
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}token={token}"


def serve_media(request, media_path):
    """Serve /media/<path>. Sensitive paths require a valid signed token."""
    if _is_sensitive(media_path):
        token = request.GET.get("token")
        if not token:
            return HttpResponse("token required", status=401)
        try:
            payload = _SIGNER.unsign(token, max_age=_MAX_AGE)
        except SignatureExpired:
            return HttpResponse("token expired", status=401)
        except BadSignature:
            return HttpResponse("bad token", status=401)
        # payload = "<user_id>:<path>"; enforce path binding
        try:
            _, signed_path = payload.split(":", 1)
        except ValueError:
            return HttpResponse("malformed token", status=401)
        if signed_path != media_path:
            return HttpResponse("path mismatch", status=401)
    try:
        abs_path = safe_join(settings.MEDIA_ROOT, media_path)
    except (ValueError, SuspiciousFileOperation):
        raise Http404()
    if not os.path.isfile(abs_path):
        raise Http404()
    return FileResponse(open(abs_path, "rb"))
