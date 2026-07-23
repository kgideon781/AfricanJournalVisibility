from public_pages.sitemaps import _CanonicalDomainMixin
from django.contrib.sitemaps import Sitemap

from .models import GreyLiterature


class GreyLiteratureSitemap(_CanonicalDomainMixin, Sitemap):
    """Sitemap for approved grey-literature items. Landing pages ship in the
    next round; the canonical URL path is reserved here so crawlers pick up
    the entries as soon as the pages exist.
    """
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return GreyLiterature.objects.filter(approved=True).only(
            "id", "slug", "updated_at"
        ).order_by("id")

    def location(self, obj):
        return f"/grey/{obj.slug}/"

    def lastmod(self, obj):
        return obj.updated_at
