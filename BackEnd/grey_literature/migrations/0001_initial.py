from django.conf import settings
from django.db import migrations, models
import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("journalApis", "0021_article_pdf_text_search_vector"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GreyLiterature",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.TextField()),
                ("slug", models.SlugField(blank=True, max_length=255, unique=True)),
                ("item_type", models.CharField(
                    choices=[
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
                    ],
                    default="other",
                    max_length=32,
                )),
                ("authors", models.TextField(help_text="Comma-separated list of authors.")),
                ("issuing_organization", models.CharField(blank=True, max_length=512, null=True)),
                ("abstract", models.TextField(blank=True, null=True)),
                ("keywords", models.TextField(blank=True, help_text="Comma-separated tags.", null=True)),
                ("sub_region", models.CharField(
                    blank=True,
                    help_text='Free-text sub-region label, e.g. "East Africa", "SADC".',
                    max_length=128,
                    null=True,
                )),
                ("language", models.CharField(blank=True, max_length=8, null=True)),
                ("publication_date", models.DateField(blank=True, null=True)),
                ("source", models.TextField(
                    blank=True,
                    help_text="Provenance: where the item came from / how it was obtained.",
                    null=True,
                )),
                ("doi", models.CharField(blank=True, max_length=255, null=True)),
                ("file", models.FileField(blank=True, null=True, upload_to="grey/")),
                ("pdf_text", models.TextField(blank=True, null=True)),
                ("search_vector", django.contrib.postgres.search.SearchVectorField(blank=True, null=True)),
                ("approved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("country", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="grey_literature",
                    to="journalApis.country",
                )),
                ("user", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="grey_literature_submissions",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Grey Literature Item",
                "verbose_name_plural": "Grey Literature",
                "ordering": ["-publication_date", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="greyliterature",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector"], name="grey_search_vector_gin"
            ),
        ),
        migrations.AddIndex(
            model_name="greyliterature",
            index=models.Index(fields=["approved", "publication_date"], name="grey_lit_approved_pubdate_idx"),
        ),
        migrations.AddIndex(
            model_name="greyliterature",
            index=models.Index(fields=["item_type"], name="grey_lit_item_type_idx"),
        ),
    ]
