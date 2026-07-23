from django.db import migrations, models


def backfill(apps, schema_editor):
    """Copy old single-value data into new multi-value + status fields.

    - Journal.thematic_area (single FK) -> disciplines (M2M) as one entry
    - Journal.language (single FK)       -> languages (M2M) as one entry
    - Journal.approved (bool)            -> status = approved / pending
    - Article.authors (text CSV)         -> authors_json = [{"name": ...}, ...]
    - Article.status                     -> published if journal.approved else draft
    """
    Journal = apps.get_model("journalApis", "Journal")
    Article = apps.get_model("journalApis", "Article")

    approved_ids = set(Journal.objects.filter(approved=True).values_list("id", flat=True))
    print(f"    backfill: {len(approved_ids)} approved journals")

    journal_updates = 0
    for j in Journal.objects.only("id", "thematic_area_id", "language_id", "approved").iterator(chunk_size=500):
        if j.thematic_area_id:
            j.disciplines.add(j.thematic_area_id)
        if j.language_id:
            j.languages.add(j.language_id)
        new_status = "approved" if j.approved else "pending"
        Journal.objects.filter(pk=j.pk).update(status=new_status)
        journal_updates += 1
    print(f"    backfill: {journal_updates} journals updated")

    article_updates = 0
    batch = []
    BATCH_SIZE = 500
    for a in Article.objects.only("id", "authors", "journal_id").iterator(chunk_size=BATCH_SIZE):
        authors_list = [{"name": name.strip()} for name in (a.authors or "").split(",") if name.strip()]
        new_status = "published" if a.journal_id in approved_ids else "draft"
        a.authors_json = authors_list
        a.status = new_status
        batch.append(a)
        if len(batch) >= BATCH_SIZE:
            Article.objects.bulk_update(batch, ["authors_json", "status"])
            article_updates += len(batch)
            batch = []
    if batch:
        Article.objects.bulk_update(batch, ["authors_json", "status"])
        article_updates += len(batch)
    print(f"    backfill: {article_updates} articles updated")


def unbackfill(apps, schema_editor):
    """No-op reverse: additive migration, old fields still present."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("journalApis", "0021_article_pdf_text_search_vector"),
    ]

    operations = [
        # Journal: additive fields per concept-doc §11
        migrations.AddField(
            model_name="journal",
            name="disciplines",
            field=models.ManyToManyField(
                blank=True, related_name="journals_multi",
                to="journalApis.thematicarea",
            ),
        ),
        migrations.AddField(
            model_name="journal",
            name="languages",
            field=models.ManyToManyField(
                blank=True, related_name="journals_multi",
                to="journalApis.language",
            ),
        ),
        migrations.AddField(
            model_name="journal",
            name="doi_prefix",
            field=models.CharField(
                blank=True, null=True, max_length=32,
                help_text="CrossRef DOI prefix, e.g. 10.55555.",
            ),
        ),
        migrations.AddField(
            model_name="journal",
            name="indexed_in",
            field=models.JSONField(
                blank=True, default=dict,
                help_text="Flags like {scopus: true, wos: false, doaj: true}.",
            ),
        ),
        migrations.AddField(
            model_name="journal",
            name="status",
            field=models.CharField(
                default="pending", max_length=16,
                choices=[
                    ("draft", "Draft"),
                    ("pending", "Pending review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("suspended", "Suspended"),
                ],
                help_text="Richer replacement for the approved boolean.",
            ),
        ),
        # Article: additive fields
        migrations.AddField(
            model_name="article",
            name="authors_json",
            field=models.JSONField(
                blank=True, default=list,
                help_text="List of {name, orcid?, affiliation?} objects.",
            ),
        ),
        migrations.AddField(
            model_name="article",
            name="status",
            field=models.CharField(
                default="draft", max_length=16,
                choices=[
                    ("draft", "Draft"),
                    ("published", "Published"),
                    ("retracted", "Retracted"),
                    ("withdrawn", "Withdrawn"),
                ],
            ),
        ),
        migrations.RunPython(backfill, reverse_code=unbackfill),
    ]
