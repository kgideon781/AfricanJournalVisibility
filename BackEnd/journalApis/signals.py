from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Article
from .tasks import extract_article_pdf, refresh_article_search_vector


@receiver(post_save, sender=Article, dispatch_uid="journalApis.article_search_index")
def article_index_hook(sender, instance, created, **kwargs):
    """Keep Article.search_vector in sync; kick off PDF extraction if needed."""
    try:
        refresh_article_search_vector.delay(instance.pk)
    except Exception:
        refresh_article_search_vector(instance.pk)

    if instance.pdf and not instance.pdf_text:
        try:
            extract_article_pdf.delay(instance.pk)
        except Exception:
            extract_article_pdf(instance.pk)
