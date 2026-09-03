"""Duplicate-complaint detection.

Closes the "50 people report the same pothole = 50 tickets" gap. This is a
deliberately simple heuristic for the hackathon build: same category and an
exact (normalized) location match, still open, reported within the last
DUPLICATE_WINDOW_DAYS days. A new report matching an existing one is merged
into it (the reporter is added to `reporters`) instead of creating a new
complaint.

Known limitation (documented, not solved here): location is free-text, so
"Main St & 5th Ave" and "5th and Main" won't match. A production version
needs geocoding to cluster reports within a radius rather than exact string
match — see ARCHITECTURE.md section on duplicate detection.
"""
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from app.models import Complaint, Status
from app.tools import normalize_location

DUPLICATE_WINDOW_DAYS = 14

_OPEN_STATUSES = {Status.PREPARED, Status.SUBMITTED, Status.FOLLOWED_UP, Status.ESCALATED}


def find_duplicate(existing: Iterable[Complaint], category: str, location: str) -> Optional[Complaint]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=DUPLICATE_WINDOW_DAYS)
    target_location = normalize_location(location)
    for complaint in existing:
        if complaint.status not in _OPEN_STATUSES:
            continue
        if complaint.category != category:
            continue
        if normalize_location(complaint.location) != target_location:
            continue
        if datetime.fromisoformat(complaint.created_at) < cutoff:
            continue
        return complaint
    return None
