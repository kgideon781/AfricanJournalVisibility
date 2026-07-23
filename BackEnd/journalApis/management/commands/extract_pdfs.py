from django.core.management.base import BaseCommand
from django.db.models import Q

from journalApis.models import Article
from journalApis.tasks import (
    _extract_pdf_text,
    _weighted_search_vector,
)


class Command(BaseCommand):
    help = (
        "Extract text from Article.pdf files and populate pdf_text + search_vector. "
        "Runs inline (no Celery) so it can be resumed after interrupts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Stop after processing N articles this run.",
        )
        parser.add_argument(
            "--batch-size", type=int, default=100,
            help="How many articles to fetch per DB round-trip.",
        )
        parser.add_argument(
            "--force", action="store_true",
            help="Re-extract even for articles that already have pdf_text.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be processed without touching the DB.",
        )
        parser.add_argument(
            "--only-id", type=int, default=None,
            help="Process a single article by id (for debugging).",
        )
        parser.add_argument(
            "--refresh-vector-only", action="store_true",
            help="Skip PDF extraction; just recompute search_vector from existing text fields.",
        )

    def handle(self, *args, **opts):
        qs = Article.objects.exclude(pdf="").exclude(pdf__isnull=True)

        if opts["only_id"]:
            qs = Article.objects.filter(pk=opts["only_id"])
        elif not opts["force"] and not opts["refresh_vector_only"]:
            qs = qs.filter(Q(pdf_text__isnull=True) | Q(pdf_text=""))

        qs = qs.order_by("pk").only("id", "pdf", "pdf_text")

        total_target = qs.count() if opts["limit"] is None else min(qs.count(), opts["limit"])
        self.stdout.write(f"Candidates: {total_target}")

        if opts["dry_run"]:
            return

        processed = 0
        extracted = 0
        skipped_no_path = 0
        empty_pdfs = 0
        errors = 0

        pks = list(qs.values_list("pk", flat=True)[:opts["limit"]]) if opts["limit"] else list(qs.values_list("pk", flat=True))

        batch = opts["batch_size"]
        for i in range(0, len(pks), batch):
            chunk = pks[i:i + batch]
            for pk in chunk:
                article = Article.objects.only("id", "pdf", "pdf_text").filter(pk=pk).first()
                if article is None:
                    continue

                if opts["refresh_vector_only"]:
                    Article.objects.filter(pk=pk).update(search_vector=_weighted_search_vector())
                    processed += 1
                    continue

                try:
                    pdf_path = article.pdf.path
                except (ValueError, NotImplementedError):
                    skipped_no_path += 1
                    processed += 1
                    continue

                text = _extract_pdf_text(pdf_path)
                if text is None:
                    errors += 1
                    processed += 1
                    continue

                if not text:
                    empty_pdfs += 1

                Article.objects.filter(pk=pk).update(pdf_text=text, search_vector=_weighted_search_vector())
                extracted += 1
                processed += 1

            self.stdout.write(
                f"  processed={processed} extracted={extracted} "
                f"empty={empty_pdfs} no_path={skipped_no_path} errors={errors}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"Done. processed={processed} extracted={extracted} "
            f"empty={empty_pdfs} no_path={skipped_no_path} errors={errors}"
        ))
