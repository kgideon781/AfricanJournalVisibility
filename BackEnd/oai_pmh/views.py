from datetime import datetime, timezone

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .verbs import VERB_HANDLERS, OaiError


ALLOWED_METHODS = ("GET", "POST")


@method_decorator(csrf_exempt, name="dispatch")
class OaiView(View):
    """Single dispatcher for all six OAI-PMH verbs.

    Both GET and POST are permitted per OAI-PMH 2.0 §3.1.1.
    """

    def get(self, request, *args, **kwargs):
        return self._handle(request)

    def post(self, request, *args, **kwargs):
        return self._handle(request)

    # ------------------------------------------------------------------

    def _handle(self, request):
        params = dict(request.GET.items()) if request.method == "GET" else dict(request.POST.items())
        verb = params.get("verb", "")

        base_ctx = {
            "response_date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "request_url": self._request_url(request),
            "request_params": params,
        }

        handler = VERB_HANDLERS.get(verb)
        if handler is None:
            return self._error(base_ctx, "badVerb", f"Unknown or missing verb: {verb!r}")

        try:
            template_name, ctx = handler(request, params)
        except OaiError as exc:
            return self._error(base_ctx, exc.code, exc.message)

        ctx = {**base_ctx, **ctx}
        body = render_to_string(template_name, ctx)
        return HttpResponse(body, content_type="application/xml; charset=utf-8")

    # ------------------------------------------------------------------

    def _error(self, base_ctx, code, message=""):
        ctx = {**base_ctx, "error_code": code, "error_message": message}
        body = render_to_string("oai_pmh/error.xml", ctx)
        # Per OAI-PMH, error responses still use 200 OK.
        return HttpResponse(body, content_type="application/xml; charset=utf-8")

    def _request_url(self, request):
        from django.conf import settings
        site = getattr(settings, "SITE_URL", None)
        if site:
            return f"{site.rstrip('/')}{request.path}"
        return request.build_absolute_uri(request.path)
