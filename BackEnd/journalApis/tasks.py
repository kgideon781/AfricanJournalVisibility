from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task
from django.contrib.postgres.search import SearchVector
from django.db.models import TextField, Value
from django.db.models.functions import Coalesce

from .models import Article

logger = logging.getLogger(__name__)

FTS_CONFIG = "english"


def _coalesce_text(field):
    return Coalesce(field, Value(""), output_field=TextField())


def _weighted_search_vector():
    return (
        SearchVector(_coalesce_text("title"), weight="A", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("keywords"), weight="A", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("authors"), weight="B", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("abstract"), weight="B", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("subjects"), weight="B", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("article_type"), weight="C", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("publisher"), weight="C", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("pdf_text"), weight="D", config=FTS_CONFIG)
    )


@shared_task
def refresh_article_search_vector(article_id):
    """Recompute Article.search_vector for one row from its current text fields."""
    Article.objects.filter(pk=article_id).update(
        search_vector=_weighted_search_vector()
    )


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def extract_article_pdf(self, article_id):
    """Extract text from Article.pdf with PyMuPDF, store in pdf_text, refresh tsvector."""
    try:
        article = Article.objects.only("id", "pdf").get(pk=article_id)
    except Article.DoesNotExist:
        logger.warning("extract_article_pdf: article %s no longer exists", article_id)
        return

    if not article.pdf:
        logger.info("extract_article_pdf: article %s has no pdf, skipping", article_id)
        return

    try:
        pdf_path = article.pdf.path
    except (ValueError, NotImplementedError):
        logger.warning("extract_article_pdf: article %s pdf has no local path", article_id)
        return

    text = _extract_pdf_text(pdf_path)
    if text is None:
        return

    Article.objects.filter(pk=article_id).update(pdf_text=text)
    refresh_article_search_vector(article_id)


def _extract_pdf_text(path):
    """Return extracted text (possibly empty for scanned PDFs), or None on error."""
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(path)
    except Exception as exc:
        logger.warning("PyMuPDF could not open %s: %s", path, exc)
        return None

    try:
        pieces = []
        for page in doc:
            try:
                pieces.append(page.get_text("text") or "")
            except Exception as exc:
                logger.warning("PyMuPDF page extract failed for %s: %s", path, exc)
        return "\n".join(pieces).strip()
    finally:
        doc.close()
