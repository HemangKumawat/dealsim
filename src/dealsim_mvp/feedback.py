"""
Feedback collection for DealSim.

Stores user ratings and comments alongside session context
(score, scenario type) in a JSONL file. No PII beyond an optional email.

Unit convention: timestamps are ISO 8601 UTC strings.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("DEALSIM_DATA_DIR", "data"))


class FeedbackCollector:
    """Append-only feedback store backed by a JSONL file."""

    # Summary cache: avoids full JSONL scan on every admin dashboard hit.
    _SUMMARY_CACHE_TTL: float = 60.0

    def __init__(self, file_path: str | None = None):
        self._path = Path(file_path) if file_path else _DATA_DIR / "feedback.jsonl"
        self._lock = threading.Lock()
        self._summary_cache: dict | None = None
        self._summary_cache_ts: float = 0.0
        self._ensure_dir()

    # -- Core API -------------------------------------------------------------

    def submit(
        self,
        session_id: str,
        rating: int,
        comment: str = "",
        email: str | None = None,
        score: int | None = None,
        scenario_type: str | None = None,
    ) -> None:
        """Store one feedback record with session context.

        Args:
            session_id: The negotiation session this feedback refers to.
            rating: 1-5 star rating.
            comment: Free-text comment (max 1000 chars, truncated here).
            email: Optional contact email (stored only if user provides it).
            score: Final negotiation score for context.
            scenario_type: Which scenario was played.
        """
        record = {
            "session_id": session_id,
            "rating": max(1, min(5, rating)),
            "comment": (comment or "")[:1000],
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        if email:
            record["email"] = email[:200]
        if score is not None:
            record["final_score"] = score
        if scenario_type:
            record["scenario_type"] = scenario_type

        self._append(record)
        # Invalidate cache so the next get_summary() reflects this submission.
        self._summary_cache = None

    # -- Aggregation ----------------------------------------------------------

    def get_summary(self) -> dict[str, Any]:
        """Aggregate feedback data for the admin dashboard.

        Results are cached for _SUMMARY_CACHE_TTL seconds (60 s).
        Invalidated automatically on the next submit() call so fresh
        feedback shows up within one TTL window.

        Returns:
            total_feedback, average_rating, rating_distribution,
            recent_comments, feedback_with_email_count
        """
        now = time.monotonic()
        if (
            self._summary_cache is not None
            and (now - self._summary_cache_ts) < self._SUMMARY_CACHE_TTL
        ):
            return self._summary_cache

        result = self._compute_summary()
        self._summary_cache = result
        self._summary_cache_ts = now
        return result

    def _compute_summary(self) -> dict[str, Any]:
        """Full JSONL scan — called by get_summary() at most once per TTL."""
        records = self._read_all()

        ratings = [r["rating"] for r in records if "rating" in r]
        average_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        rating_dist: Counter[int] = Counter()
        for r in ratings:
            rating_dist[r] += 1

        # Most recent 20 comments (with text)
        with_comments = [r for r in records if r.get("comment")]
        recent_comments = [
            {
                "rating": r["rating"],
                "comment": r["comment"],
                "submitted_at": r.get("submitted_at", ""),
                "scenario_type": r.get("scenario_type", ""),
                "final_score": r.get("final_score"),
            }
            for r in with_comments[-20:]
        ]
        recent_comments.reverse()  # newest first

        return {
            "total_feedback": len(records),
            "average_rating": average_rating,
            "rating_distribution": {str(k): v for k, v in sorted(rating_dist.items())},
            "recent_comments": recent_comments,
            "feedback_with_email_count": sum(1 for r in records if r.get("email")),
            "feedback_with_comment_count": len(with_comments),
        }

    def get_all(self) -> list[dict]:
        """Return all feedback records (for export)."""
        return self._read_all()

    # -- File rotation ---------------------------------------------------------

    _MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
    _MAX_ROTATED_FILES = 3

    def _rotate_if_needed(self) -> None:
        """Rotate the JSONL file when it exceeds _MAX_FILE_BYTES.

        Keeps at most _MAX_ROTATED_FILES rotated copies (.1, .2, .3).
        Caller must hold self._lock.
        """
        try:
            if not self._path.exists():
                return
            if self._path.stat().st_size < self._MAX_FILE_BYTES:
                return
        except OSError:
            return

        # Shift existing rotated files: .2 -> .3, .1 -> .2
        for i in range(self._MAX_ROTATED_FILES, 1, -1):
            src = Path(str(self._path) + f".{i - 1}")
            dst = Path(str(self._path) + f".{i}")
            try:
                if src.exists():
                    os.replace(str(src), str(dst))
            except OSError:
                pass

        # Delete oldest if it would exceed max count
        oldest = Path(str(self._path) + f".{self._MAX_ROTATED_FILES}")
        try:
            if oldest.exists():
                oldest.unlink()
        except OSError:
            pass

        # Current -> .1
        try:
            os.replace(str(self._path), str(self._path) + ".1")
        except OSError:
            pass

    # -- Internal helpers -----------------------------------------------------

    def _ensure_dir(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: dict) -> None:
        with self._lock:
            self._rotate_if_needed()
            try:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, default=str) + "\n")
            except Exception:
                logger.warning("Feedback write failed for %s", self._path, exc_info=True)

    def _read_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        records: list[dict] = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            logger.warning("Feedback read failed for %s", self._path, exc_info=True)
        return records


# -- Singleton ----------------------------------------------------------------

_collector: FeedbackCollector | None = None


def get_collector() -> FeedbackCollector:
    """Return (or create) the module-level FeedbackCollector singleton."""
    global _collector
    if _collector is None:
        _collector = FeedbackCollector()
    return _collector
