"""Peer-review workflow email notifications.

Public API — call these from view code after each workflow transition.
The heavy lifting (SMTP round-trip, retries) happens in a Celery task so
the request thread returns immediately even under a slow mail server.

Concept doc §8: "the system notifies the next actor automatically at each
step." Mapping:

    author submits            → editor(s) get "New manuscript to triage"
    editor assigns reviewer   → reviewer gets "You've been assigned to review"
    reviewer submits review   → editor(s) get "Review submitted, decide next"
    editor decides            → author gets "Editorial decision on your submission"
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()


# ---------------------------------------------------------------------------
# Recipient helpers

def _valid_email(addr):
    return bool(addr and "@" in addr)


def _editor_recipients(journal) -> list[str]:
    """Editors for a manuscript = journal owner + any staff user.

    Deduped and stripped of blanks/None. Concept doc doesn't yet call for
    per-journal handling editors, so this is the pragmatic reading.
    """
    emails = set()
    if journal and getattr(journal, "user_id", None) and journal.user and _valid_email(journal.user.email):
        emails.add(journal.user.email)
    for staff in User.objects.filter(is_staff=True).only("email"):
        if _valid_email(staff.email):
            emails.add(staff.email)
    return sorted(emails)


def _dashboard_url(path: str = "") -> str:
    """Build a dashboard-facing URL. Falls back to landing SITE_URL if the
    FRONTEND_URL setting isn't set."""
    base = (
        getattr(settings, "FRONTEND_URL", None)
        or getattr(settings, "SITE_URL", "")
    ).rstrip("/")
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"


# ---------------------------------------------------------------------------
# Public: 4 transition helpers

def notify_manuscript_submitted(manuscript):
    """Fires after ManuscriptCreateView creates a new Manuscript row."""
    recipients = _editor_recipients(manuscript.journal)
    if not recipients:
        logger.info("notify_manuscript_submitted: no editor emails for manuscript %s", manuscript.id)
        return
    _enqueue(
        template="manuscript_submitted",
        subject=f"[AJP] New manuscript submitted: {manuscript.title[:120]}",
        recipients=recipients,
        context={
            "manuscript_id": manuscript.id,
            "title": manuscript.title,
            "authors": manuscript.authors or "",
            "journal_title": manuscript.journal.journal_title if manuscript.journal_id else "",
            "submitter_name": _display_name(manuscript.corresponding_author),
            "editor_url": _dashboard_url(f"editors_manuscript/{manuscript.id}"),
        },
    )


def notify_reviewer_assigned(manuscript, reviewer):
    """Fires after AssignReviewerView creates a ReviewerAssignment."""
    if not _valid_email(reviewer.email):
        logger.info("notify_reviewer_assigned: reviewer %s has no email", reviewer.id)
        return
    _enqueue(
        template="reviewer_assigned",
        subject=f"[AJP] Review request: {manuscript.title[:120]}",
        recipients=[reviewer.email],
        context={
            "manuscript_id": manuscript.id,
            "title": manuscript.title,
            "authors": manuscript.authors or "",
            "abstract": manuscript.abstract or "",
            "journal_title": manuscript.journal.journal_title if manuscript.journal_id else "",
            "reviewer_name": _display_name(reviewer),
            "reviewer_url": _dashboard_url("submit_reviews"),
        },
    )


def notify_review_submitted(review):
    """Fires after SubmitReviewView saves a Review row."""
    manuscript = review.manuscript
    recipients = _editor_recipients(manuscript.journal)
    if not recipients:
        logger.info("notify_review_submitted: no editor emails for manuscript %s", manuscript.id)
        return
    _enqueue(
        template="review_submitted",
        subject=f"[AJP] Review submitted: {manuscript.title[:120]}",
        recipients=recipients,
        context={
            "manuscript_id": manuscript.id,
            "title": manuscript.title,
            "reviewer_name": _display_name(review.reviewer),
            "recommendation": review.get_recommendation_display() if hasattr(review, "get_recommendation_display") else review.recommendation,
            "score": review.score if review.score is not None else "",
            "editor_url": _dashboard_url(f"editors_manuscript/{manuscript.id}"),
        },
    )


def notify_editorial_decision(manuscript, decision, notes: str = ""):
    """Fires after EditorialDecisionView records a decision."""
    author = manuscript.corresponding_author
    if not author or not _valid_email(author.email):
        logger.info("notify_editorial_decision: author for manuscript %s has no email", manuscript.id)
        return

    decision_label = {
        "accept": "accepted",
        "reject": "rejected",
        "revise": "requires revision",
    }.get(decision, decision)

    _enqueue(
        template="editorial_decision",
        subject=f"[AJP] Editorial decision on your manuscript: {decision_label}",
        recipients=[author.email],
        context={
            "manuscript_id": manuscript.id,
            "title": manuscript.title,
            "journal_title": manuscript.journal.journal_title if manuscript.journal_id else "",
            "author_name": _display_name(author),
            "decision": decision,
            "decision_label": decision_label,
            "notes": notes or "",
            "author_url": _dashboard_url("my_manuscripts"),
        },
    )


# ---------------------------------------------------------------------------
# Internals

def _display_name(user) -> str:
    if user is None:
        return ""
    for attr in ("user_name", "get_full_name", "username", "email"):
        val = getattr(user, attr, None)
        if callable(val):
            val = val()
        if val:
            return str(val)
    return ""


def _enqueue(*, template: str, subject: str, recipients: list[str], context: dict):
    from .tasks import send_notification_email

    try:
        send_notification_email.delay(
            template=template,
            subject=subject,
            recipients=recipients,
            context=context,
        )
    except Exception as exc:  # broker down — fall back to inline send so we
        # don't silently drop notifications.
        logger.warning("Celery enqueue failed for %s, sending inline: %s", template, exc)
        send_notification_email(
            template=template,
            subject=subject,
            recipients=recipients,
            context=context,
        )
