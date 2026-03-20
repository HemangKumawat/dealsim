"""
Legacy analytics shim -- delegates to dealsim_mvp.analytics and .feedback.

Preserves backward compatibility for any code that imports from this path.
New code should import from dealsim_mvp.analytics / dealsim_mvp.feedback.
"""

from __future__ import annotations

from dealsim_mvp.analytics import get_tracker
from dealsim_mvp.feedback import get_collector


def append_event(event_type: str, properties: dict | None = None) -> None:
    """Store a privacy-respecting analytics event."""
    get_tracker().track(event_type, properties)


def append_feedback(data: dict) -> None:
    """Store a feedback record."""
    get_collector().submit(
        session_id=data.get("session_id", ""),
        rating=data.get("rating", 3),
        comment=data.get("comment", ""),
        email=data.get("email") or None,
        score=data.get("final_score"),
        scenario_type=data.get("scenario_type"),
    )


def read_events() -> list[dict]:
    """Read all event records."""
    return get_tracker().get_events(limit=100_000)


def read_feedback() -> list[dict]:
    """Read all feedback records."""
    return get_collector().get_all()
