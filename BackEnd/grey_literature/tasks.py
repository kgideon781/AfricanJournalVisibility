from __future__ import absolute_import, unicode_literals

import logging

from celery import shared_task
from django.contrib.postgres.search import SearchVector
from django.db.models import TextField, Value
from django.db.models.functions import Coalesce

from .models import GreyLiterature

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
        + SearchVector(_coalesce_text("issuing_organization"), weight="C", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("sub_region"), weight="C", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("source"), weight="C", config=FTS_CONFIG)
        + SearchVector(_coalesce_text("pdf_text"), weight="D", config=FTS_CONFIG)
    )


@shared_task
def refresh_grey_search_vector(pk):
    GreyLiterature.objects.filter(pk=pk).update(search_vector=_weighted_search_vector())


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def extract_grey_pdf(self, pk):
    try:
        item = GreyLiterature.objects.only("id", "file").get(pk=pk)
    except GreyLiterature.DoesNotExist:
        logger.warning("extract_grey_pdf: %s no longer exists", pk)
        return

    if not item.file:
        return

    try:
        path = item.file.path
    except (ValueError, NotImplementedError):
        logger.warning("extract_grey_pdf: %s file has no local path", pk)
        return

    text = _extract_pdf_text(path)
    if text is None:
        return

    GreyLiterature.objects.filter(pk=pk).update(pdf_text=text)
    refresh_grey_search_vector(pk)


def _extract_pdf_text(path):
    import fitz

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
