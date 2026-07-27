"""Bulk-upload endpoint for editor back-catalog migration.

Consumes a filled `AJP_Bulk_Upload_Template.xlsx` (the 'Articles' sheet) plus
a batch of PDF files. Validates every row, checks that the uploader owns the
referenced journals, and creates Volume + Article rows atomically.

Design notes:
- Ownership: rows are rejected unless the referenced Journal belongs to the
  uploader (Journal.user == request.user) OR the uploader is staff. Prevents
  authors from injecting articles into other people's journals.
- Idempotency: rows whose DOI already exists on an Article — or whose
  (journal, volume, issue, title) tuple already exists — are counted as
  `skipped`, not treated as errors. Reruns of the same sheet are safe.
- Volume dedup: articles pointing at the same (journal, volume_number,
  issue_number, year) share one Volume row. First row for a given tuple
  creates it; subsequent rows attach.
- The full batch is wrapped in a single transaction. If any DB write fails,
  the whole submission rolls back — the user resubmits, no half-imports.
"""
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from drf_spectacular.utils import extend_schema

from openpyxl import load_workbook

from .models import Article, Journal, Volume


SHEET_NAME_CANDIDATES = ('Articles', 'articles')
# The template's column order — used to map cells positionally when the
# header row isn't present or is customized. See AJP_Bulk_Upload_Template.xlsx.
EXPECTED_COLUMNS = [
    'journal_title', 'issn', 'volume_number', 'volume_year', 'issue_number',
    'issue_date', 'article_title', 'authors', 'abstract', 'keywords',
    'language', 'start_page', 'end_page', 'publication_date', 'doi',
    'license', 'pdf_filename',
]

# Rows the template pre-fills as instructions / examples. Skip any row whose
# first cell contains any of these phrases (case-insensitive substring).
INSTRUCTION_ROW_MARKERS = (
    'delete the yellow example',
    'required = must be filled',
    'one row per article',
)


def _cell(row, idx):
    """Safe indexed access into a tuple row — returns empty string for missing."""
    if idx < len(row):
        v = row[idx]
        if v is None:
            return ''
        return str(v).strip()
    return ''


def _is_instruction_row(first_cell):
    if not first_cell:
        return False
    lower = first_cell.lower()
    return any(m in lower for m in INSTRUCTION_ROW_MARKERS)


def _parse_int(s, field_name, row_num):
    if s is None or s == '':
        raise ValueError(f'Row {row_num}: `{field_name}` is required.')
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        raise ValueError(
            f'Row {row_num}: `{field_name}` must be an integer, got {s!r}.'
        )


def _pick_sheet(wb):
    """Prefer 'Articles' by name; else the first non-'Instructions' sheet."""
    for name in SHEET_NAME_CANDIDATES:
        if name in wb.sheetnames:
            return wb[name]
    for name in wb.sheetnames:
        if 'instructions' not in name.lower():
            return wb[name]
    return wb[wb.sheetnames[0]]


class _Row:
    """One parsed spreadsheet row with typed values."""

    __slots__ = tuple(EXPECTED_COLUMNS) + ('row_num',)

    def __init__(self, row_num, cells):
        self.row_num = row_num
        for i, name in enumerate(EXPECTED_COLUMNS):
            setattr(self, name, _cell(cells, i))


def _parse_sheet(sheet):
    """Yields (_Row, row_num). Skips header + instruction rows."""
    header_seen = False
    for i, raw in enumerate(sheet.iter_rows(values_only=True), start=1):
        cells = tuple(raw or ())
        first = _cell(cells, 0)
        if not any(str(v).strip() for v in cells if v is not None):
            continue  # blank
        if not header_seen and first.lower() == 'journal_title':
            header_seen = True
            continue
        if _is_instruction_row(first):
            continue
        if not header_seen:
            # First non-blank isn't a header — assume positional; still yield
            # everything from here on. Rare edge case.
            header_seen = True
        yield _Row(i, cells)


def _find_owned_journal(title, user):
    """Return (journal_or_none, error_message_or_none)."""
    if not title:
        return None, 'journal_title is required.'
    match = Journal.objects.filter(journal_title__iexact=title.strip())
    if not match.exists():
        return None, (
            f'No journal titled {title!r} exists in the catalogue. '
            f'Register the journal first via Submit Journal.'
        )
    # If exactly one match: check ownership
    if match.count() == 1:
        j = match.first()
        if user.is_staff or j.user_id == user.id:
            return j, None
        return None, (
            f'You do not own the journal {title!r}. Only its registered '
            f'owner can add articles to it.'
        )
    # Multiple matches (same title): pick the one the user owns
    owned = match.filter(user=user).first()
    if owned:
        return owned, None
    if user.is_staff:
        return match.first(), None
    return None, (
        f'Multiple journals titled {title!r} exist; none owned by you. '
        f'Contact staff to resolve.'
    )


def _find_pdf(filename, pdf_files):
    """Look up an UploadedFile by filename (case-insensitive)."""
    if not filename:
        return None
    lower = filename.strip().lower()
    for f in pdf_files:
        if f.name.strip().lower() == lower:
            return f
    return None


def _article_exists(journal, volume, title, doi):
    """Duplicate check: DOI first when present, else tuple."""
    if doi:
        if Article.objects.filter(doi__iexact=doi.strip()).exists():
            return True
    return Article.objects.filter(
        journal=journal, volume=volume, title__iexact=(title or '').strip()
    ).exists()


@extend_schema(
    tags=['Journals'],
    summary='Bulk-upload articles from a filled template + PDF batch (auth)',
    description=(
        'Accepts a filled AJP bulk-upload spreadsheet plus a batch of PDF '
        'files. Creates Volume + Article rows for each valid row, attaching '
        'the matching PDF. Rows referencing journals the caller does not own '
        'are rejected. Duplicates (by DOI or title-tuple) are skipped. Whole '
        'batch is atomic.'
    ),
)
class BulkArticleUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        sheet_file = request.FILES.get('sheet')
        if not sheet_file:
            return Response(
                {'error': 'No `sheet` file provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # DRF's MultiPartParser groups files by field name. `pdfs` may be
        # sent multiple times.
        pdf_files = request.FILES.getlist('pdfs') or []

        try:
            wb = load_workbook(sheet_file, data_only=True)
        except Exception as exc:
            return Response(
                {'error': f'Could not read spreadsheet: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sheet = _pick_sheet(wb)

        rows = list(_parse_sheet(sheet))
        if not rows:
            return Response(
                {'error': 'Sheet contains no article rows.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors = []
        created = 0
        skipped = 0
        created_rows = []  # (row_num, article_id) — reported on success

        # We eagerly resolve journals + volumes as we go, caching by tuple so
        # multi-row uploads for the same volume share one Volume row.
        journal_cache = {}   # title_lower -> Journal or None
        volume_cache = {}    # (journal_id, volume_number, issue_number) -> Volume

        with transaction.atomic():
            for r in rows:
                title = r.article_title
                if not title:
                    errors.append({'row': r.row_num, 'message': 'article_title is required.'})
                    continue

                # Journal (ownership-checked)
                jkey = r.journal_title.strip().lower() if r.journal_title else ''
                if jkey not in journal_cache:
                    j, jerr = _find_owned_journal(r.journal_title, request.user)
                    journal_cache[jkey] = (j, jerr)
                journal, jerr = journal_cache[jkey]
                if not journal:
                    errors.append({'row': r.row_num, 'message': jerr})
                    continue

                # Numeric fields
                try:
                    volume_number = _parse_int(r.volume_number, 'volume_number', r.row_num)
                    volume_year = _parse_int(r.volume_year, 'volume_year', r.row_num)
                    issue_number = _parse_int(r.issue_number or '1', 'issue_number', r.row_num)
                except ValueError as e:
                    errors.append({'row': r.row_num, 'message': str(e)})
                    continue

                if not r.authors:
                    errors.append({'row': r.row_num, 'message': 'authors is required.'})
                    continue

                if not r.pdf_filename:
                    errors.append({'row': r.row_num, 'message': 'pdf_filename is required.'})
                    continue

                pdf = _find_pdf(r.pdf_filename, pdf_files)
                if not pdf:
                    errors.append({
                        'row': r.row_num,
                        'message': f'PDF file {r.pdf_filename!r} not found in upload.',
                    })
                    continue

                # Volume (get-or-create, cached)
                vkey = (journal.id, volume_number, issue_number)
                if vkey not in volume_cache:
                    volume, _ = Volume.objects.get_or_create(
                        journal=journal,
                        volume_number=volume_number,
                        issue_number=issue_number,
                        defaults={'year': volume_year},
                    )
                    volume_cache[vkey] = volume
                volume = volume_cache[vkey]

                # Duplicate?
                if _article_exists(journal, volume, title, r.doi):
                    skipped += 1
                    continue

                # Parse optional publication_date (YYYY-MM-DD)
                pub_date = None
                if r.publication_date:
                    from datetime import datetime
                    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
                        try:
                            pub_date = datetime.strptime(r.publication_date, fmt).date()
                            break
                        except ValueError:
                            continue
                    if pub_date is None:
                        errors.append({
                            'row': r.row_num,
                            'message': (
                                f'publication_date {r.publication_date!r} '
                                f'must be YYYY-MM-DD.'
                            ),
                        })
                        continue

                article = Article.objects.create(
                    journal=journal,
                    volume=volume,
                    title=title,
                    authors=r.authors,
                    keywords=r.keywords or '',
                    abstract=r.abstract or '',
                    language=r.language or None,
                    doi=r.doi or None,
                    license_url=r.license or None,
                    page_start=r.start_page or None,
                    page_end=r.end_page or None,
                    publication_date=pub_date,
                    pdf=pdf,
                )
                created += 1
                created_rows.append({'row': r.row_num, 'article_id': article.id})

            # If nothing was created AND every row errored, roll back so we
            # don't leave orphan Volumes behind. Otherwise commit.
            if created == 0 and skipped == 0:
                transaction.set_rollback(True)

        return Response(
            {
                'created': created,
                'skipped': skipped,
                'errors': errors,
                'created_rows': created_rows,
            },
            status=(
                status.HTTP_400_BAD_REQUEST
                if created == 0 and skipped == 0
                else status.HTTP_200_OK
            ),
        )
