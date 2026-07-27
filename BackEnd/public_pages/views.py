"""Server-rendered, crawler-friendly landing pages for hosted journals and
articles. The single reason this exists: Google Scholar and most academic
indexers do not execute JavaScript, so the `citation_*` meta tags MUST appear
in the initial HTML response. Everything here optimizes for that.
"""
from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from journalApis.models import Article, Journal


def _split_authors(raw):
    """Article.authors is a free-text column. Best-effort split into a list."""
    if not raw:
        return []
    seps = [';', '\n']
    parts = [raw]
    for sep in seps:
        new_parts = []
        for p in parts:
            new_parts.extend(p.split(sep))
        parts = new_parts
    # Comma is common but so is "Surname, First" — treat comma-split only if
    # there's no semicolon to hint at author boundaries.
    if len(parts) == 1 and ';' not in raw and '\n' not in raw:
        parts = raw.split(',')
    out = []
    for p in parts:
        s = p.strip()
        if s:
            out.append(s)
    return out


def _split_keywords(raw):
    if not raw:
        return []
    for sep in [';', ',', '\n']:
        if sep in raw:
            return [k.strip() for k in raw.split(sep) if k.strip()]
    return [raw.strip()] if raw.strip() else []


# Minimum mapping from the language names the Language table stores to ISO
# 639-1 codes. Scholar reads citation_language and <html lang> as ISO codes;
# anything else is silently ignored. Extend when we add coverage.
_LANG_NAME_TO_ISO = {
    'english': 'en',
    'french': 'fr',
    'français': 'fr',
    'francais': 'fr',
    'portuguese': 'pt',
    'português': 'pt',
    'portugues': 'pt',
    'arabic': 'ar',
    'العربية': 'ar',
    'spanish': 'es',
    'español': 'es',
    'espanol': 'es',
    'swahili': 'sw',
    'kiswahili': 'sw',
    'amharic': 'am',
    'hausa': 'ha',
    'yoruba': 'yo',
    'igbo': 'ig',
    'zulu': 'zu',
    'afrikaans': 'af',
}


def _to_iso_lang(name):
    if not name:
        return None
    s = str(name).strip()
    if not s:
        return None
    lower = s.lower()
    if lower in _LANG_NAME_TO_ISO:
        return _LANG_NAME_TO_ISO[lower]
    # Already a 2-letter code? Take it verbatim.
    if len(s) == 2 and s.isalpha():
        return s.lower()
    return None  # Unknown — emit nothing rather than a wrong tag.


def _article_language(article):
    """Returns an ISO 639-1 code or None. Scholar drops anything else."""
    if article.language:
        iso = _to_iso_lang(article.language)
        if iso:
            return iso
    if article.journal and article.journal.language:
        return _to_iso_lang(getattr(article.journal.language, 'language', None))
    return None


def _publisher(article):
    if article.publisher:
        return article.publisher
    if article.journal and article.journal.publishers_name:
        return article.journal.publishers_name
    return None


def _absolute(url):
    """Turn a media path (e.g. '/media/articles/pdfs/x.pdf') into an absolute
    URL using SITE_URL. Scholar's citation_pdf_url and canonical MUST be
    absolute — relative URLs are silently ignored by many crawlers."""
    if not url:
        return None
    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    if url.startswith('http://') or url.startswith('https://'):
        return url
    if not url.startswith('/'):
        url = '/' + url
    return f'{base}{url}'


def _journal_qs():
    """Base queryset: approved journals only. Crawlers must not see drafts."""
    return Journal.objects.filter(approved=True)


def _article_qs():
    """Articles whose parent journal is approved. Drafts / unapproved-parent
    articles are hidden from crawlers to avoid indexing to-be-retracted URLs.
    """
    return Article.objects.filter(journal__approved=True).select_related(
        'journal', 'journal__language', 'journal__country',
        'journal__thematic_area', 'volume',
    )


# ─── Views ───────────────────────────────────────────────────────────────────

def journal_landing(request, slug):
    """/journals/<slug>/ — a journal's public page. Emits citation_journal_title,
    citation_issn and links to its articles (if any). Directory-only journals
    (no articles hosted yet) still render, pointing at the external URL — this
    preserves discoverability of the directory itself per the concept doc."""
    journal = get_object_or_404(_journal_qs(), slug=slug)

    volumes = list(
        journal.volumes.all().order_by('-year', '-volume_number', 'issue_number')
    )
    articles = list(
        _article_qs()
        .filter(journal_id=journal.id)
        .order_by('-publication_date', 'title')
    )
    articles_by_volume = {}
    orphan_articles = []  # Articles without a volume FK — happens for auto-
                          # generated articles coming out of the peer-review
                          # flow. We still list them so they're discoverable.
    for a in articles:
        if a.volume_id:
            articles_by_volume.setdefault(a.volume_id, []).append(a)
        else:
            orphan_articles.append(a)

    canonical_path = f'/journals/{journal.slug}/'
    context = {
        'journal': journal,
        'volumes': volumes,
        'articles_by_volume': articles_by_volume,
        'orphan_articles': orphan_articles,
        'article_count': len(articles),
        'canonical_url': _absolute(canonical_path),
        'site_name': 'Afrika Journals',
    }
    return TemplateResponse(request, 'public_pages/journal.html', context)


def article_landing(request, slug, article_id):
    """/journals/<slug>/articles/<id>/ — the money page for discoverability.
    The <head> block emits the full Scholar citation_* tag set (see template).
    Body carries the full abstract so crawlers and human readers both find it.
    """
    journal = get_object_or_404(_journal_qs(), slug=slug)
    article = get_object_or_404(_article_qs(), id=article_id, journal_id=journal.id)

    # Prefer the article's own volume; fall back to journal-level context.
    volume = article.volume

    pdf_url = None
    if article.pdf:
        try:
            pdf_url = _absolute(article.pdf.url)
        except Exception:
            # File field can raise if the storage backend is misconfigured.
            pdf_url = None

    canonical_path = f'/journals/{journal.slug}/articles/{article.id}/'

    context = {
        'journal': journal,
        'volume': volume,
        'article': article,
        'authors': _split_authors(article.authors),
        'keywords': _split_keywords(article.keywords),
        'language': _article_language(article),
        'publisher': _publisher(article),
        'pdf_url': pdf_url,
        'canonical_url': _absolute(canonical_path),
        'site_name': 'Afrika Journals',
    }
    return TemplateResponse(request, 'public_pages/article.html', context)


def robots_txt(request):
    """/robots.txt — text/plain. Points crawlers at the sitemap and keeps
    them out of API + admin + dashboard routes. Media (article PDFs) is
    intentionally NOT disallowed — Scholar needs to fetch PDFs to index them.
    """
    base = getattr(settings, 'SITE_URL', 'https://afrikajournals.org').rstrip('/')
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        'Disallow: /api/',
        'Disallow: /authApi/',
        'Disallow: /journal_api/',
        'Disallow: /dashboard/',
        '',
        f'Sitemap: {base}/sitemap.xml',
        '',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')
