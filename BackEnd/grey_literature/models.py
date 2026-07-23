from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.text import slugify


GREY_LIT_TYPES = [
    ("policy_brief", "Policy Brief"),
    ("working_paper", "Working Paper"),
    ("technical_report", "Technical Report"),
    ("evaluation_report", "Evaluation Report"),
    ("thesis", "Thesis"),
    ("dissertation", "Dissertation"),
    ("conference_proceedings", "Conference Proceedings"),
    ("government_report", "Government Report"),
    ("blog", "Blog"),
    ("newsletter", "Newsletter"),
    ("dataset", "Dataset"),
    ("other", "Other"),
]


class GreyLiterature(models.Model):
    """Non-journal knowledge item: policy briefs, reports, theses, datasets.

    Fields translated from AJP_Concept_Note §9 / §11 into the current
    Django + Postgres stack (no Supabase/RLS/UUID).
    """

    title = models.TextField()
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    item_type = models.CharField(max_length=32, choices=GREY_LIT_TYPES, default="other")

    authors = models.TextField(help_text="Comma-separated list of authors.")
    issuing_organization = models.CharField(max_length=512, blank=True, null=True)

    abstract = models.TextField(blank=True, null=True)
    keywords = models.TextField(blank=True, null=True, help_text="Comma-separated tags.")

    country = models.ForeignKey(
        "journalApis.Country",
        on_delete=models.SET_NULL,
        related_name="grey_literature",
        null=True,
        blank=True,
    )
    sub_region = models.CharField(
        max_length=128, blank=True, null=True,
        help_text='Free-text sub-region label, e.g. "East Africa", "SADC".',
    )

    language = models.CharField(max_length=8, blank=True, null=True)
    publication_date = models.DateField(blank=True, null=True)
    source = models.TextField(
        blank=True, null=True,
        help_text="Provenance: where the item came from / how it was obtained.",
    )
    doi = models.CharField(max_length=255, blank=True, null=True)

    file = models.FileField(upload_to="grey/", blank=True, null=True)
    pdf_text = models.TextField(blank=True, null=True)
    search_vector = SearchVectorField(blank=True, null=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="grey_literature_submissions",
        null=True,
        blank=True,
    )
    approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Grey Literature Item"
        verbose_name_plural = "Grey Literature"
        indexes = [
            GinIndex(fields=["search_vector"], name="grey_search_vector_gin"),
            models.Index(fields=["approved", "publication_date"]),
            models.Index(fields=["item_type"]),
        ]
        ordering = ["-publication_date", "-created_at"]

    def __str__(self):
        return f"{self.id} — {self.title[:80]}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "grey-item"
            candidate, i = base, 1
            while GreyLiterature.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                i += 1
                candidate = f"{base}-{i}"
            self.slug = candidate
        super().save(*args, **kwargs)
