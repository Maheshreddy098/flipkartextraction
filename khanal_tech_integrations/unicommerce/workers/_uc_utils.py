"""Shared constants and helpers for Unicommerce worker modules."""

from __future__ import annotations

from datetime import datetime

COMPLETED_PO_STATUSES: frozenset[str] = frozenset(
    {"GRN_COMPLETED", "COMPLETE", "COMPLETED", "CLOSED"}
)
MAX_GRN_ROUNDS = 200


def _to_uc_datetime(d) -> str | None:
    """Convert a date/datetime/string to Unicommerce UTC ISO 8601 format."""
    if d is None:
        return None
    if isinstance(d, str):
        if not d:
            return None
        try:
            d = datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            try:
                d = datetime.fromisoformat(d)
            except ValueError:
                return None
    if not isinstance(d, datetime):
        d = datetime(d.year, d.month, d.day)
    return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")
