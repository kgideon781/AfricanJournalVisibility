from django.db import migrations
from django.utils.text import slugify


def backfill(apps, schema_editor):
    Journal = apps.get_model('journalApis', 'Journal')
    used = set()
    # Deterministic order so collision resolution is reproducible.
    for journal in Journal.objects.order_by('id').only('id', 'journal_title', 'slug'):
        if journal.slug:
            used.add(journal.slug)
            continue
        base = slugify(journal.journal_title or '')[:180]
        if not base:
            base = f'journal-{journal.id}'
        candidate = base
        if candidate in used:
            candidate = f'{base[:170]}-{journal.id}'
        # Extremely defensive: if even the id-suffixed slug collides, keep
        # appending until it doesn't. In practice this never fires because id
        # is unique per row.
        n = 2
        while candidate in used:
            candidate = f'{base[:160]}-{journal.id}-{n}'
            n += 1
        used.add(candidate)
        journal.slug = candidate[:200]
        journal.save(update_fields=['slug'])


def reverse(apps, schema_editor):
    # Reversal just nulls the field; the AlterField in 0019's reverse drops it.
    Journal = apps.get_model('journalApis', 'Journal')
    Journal.objects.update(slug=None)


class Migration(migrations.Migration):
    dependencies = [
        ('journalApis', '0019_article_language_article_updated_at_journal_slug'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse),
    ]
