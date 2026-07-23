from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import GreyLiterature
from .tasks import extract_grey_pdf, refresh_grey_search_vector


@receiver(post_save, sender=GreyLiterature, dispatch_uid="grey_literature.index_hook")
def grey_index_hook(sender, instance, created, **kwargs):
    """Keep search_vector in sync; extract PDF text when a new file lands."""
    try:
        refresh_grey_search_vector.delay(instance.pk)
    except Exception:
        refresh_grey_search_vector(instance.pk)

    if instance.file and not instance.pdf_text:
        try:
            extract_grey_pdf.delay(instance.pk)
        except Exception:
            extract_grey_pdf(instance.pk)
