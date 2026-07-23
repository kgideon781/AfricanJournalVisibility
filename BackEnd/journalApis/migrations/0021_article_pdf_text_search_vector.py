from django.db import migrations, models
import django.contrib.postgres.search
import django.contrib.postgres.indexes


class Migration(migrations.Migration):

    dependencies = [
        ('journalApis', '0020_backfill_journal_slugs'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='pdf_text',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='article',
            name='search_vector',
            field=django.contrib.postgres.search.SearchVectorField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='article',
            index=django.contrib.postgres.indexes.GinIndex(
                fields=['search_vector'], name='article_search_vector_gin'
            ),
        ),
    ]
