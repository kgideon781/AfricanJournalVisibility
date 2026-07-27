"""Sitemap classes for hosted journals and articles. Consumed by
`django.contrib.sitemaps.views.sitemap` in the root urlconf.

Both sitemaps expose ONLY content that would render at the corresponding
landing view — i.e. approved journals and articles whose parent journal is
approved. Anything a crawler couldn't actually visit doesn't belong in the
sitemap.
"""
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sitemaps import Sitemap

from journalApis.models import Article, Journal


class _CanonicalDomainMixin:
    """Force sitemap URLs to use the canonical SITE_URL, not whatever Host
    header the request carried. Otherwise a request via IP or an unexpected
    domain would produce a sitemap with the wrong URLs — and crawlers cache
    sitemaps aggressively.
    """

    protocol = 'https'

    def get_urls(self, page=1, site=None, protocol=None):
        base = getattr(settings, 'SITE_URL', 'https://afrikajournals.org')
        parsed = urlparse(base)

        class _StubSite:
            domain = parsed.netloc
            name = parsed.netloc

        return super().get_urls(
            page=page,
            site=_StubSite(),
            protocol=parsed.scheme or 'https',
        )


class JournalSitemap(_CanonicalDomainMixin, Sitemap):
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        return Journal.objects.filter(approved=True).only(
            'id', 'slug', 'created_at'
        ).order_by('id')

    def location(self, obj):
        return f'/journals/{obj.slug}/'

    def lastmod(self, obj):
        # Journal doesn't yet have `updated_at`; created_at is truthful enough.
        return obj.created_at


class ArticleSitemap(_CanonicalDomainMixin, Sitemap):
    changefreq = 'monthly'
    priority = 0.7

    def items(self):
        return (
            Article.objects.filter(journal__approved=True)
            .select_related('journal')
            .only('id', 'updated_at', 'journal__slug')
            .order_by('id')
        )

    def location(self, obj):
        return f'/journals/{obj.journal.slug}/articles/{obj.id}/'

    def lastmod(self, obj):
        return obj.updated_at


SITEMAPS = {
    'journals': JournalSitemap,
    'articles': ArticleSitemap,
}
