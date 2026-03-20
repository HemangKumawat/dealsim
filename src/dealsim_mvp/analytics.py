"""
Usage tracking system for DealSim.

Privacy-respecting analytics stored as newline-delimited JSON (JSONL).
No cookies, no PII, no third-party services. All data stays on disk.

Events tracked:
- session_created, message_sent, simulation_completed
- debrief_viewed, playbook_generated, offer_analyzed
- challenge_completed, feedback_submitted, feature_used

Unit convention: all timestamps are ISO 8601 UTC strings.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("DEALSIM_DATA_DIR", "data"))

# Feature categories mapped from API endpoint paths.
# Used by the tracking middleware to auto-tag every request.
ENDPOINT_FEATURE_MAP: dict[str, str] = {
    "/api/sessions": "simulation",
    "/api/sessions/{session_id}/message": "simulation",
    "/api/sessions/{session_id}/complete": "debrief",
    "/api/debrief": "debrief",
    "/api/playbook": "playbook",
    "/api/offer-analyzer": "offer_analyzer",
    "/api/daily-challenge": "daily_challenge",
    "/api/earnings-calculator": "earnings_calculator",
    "/api/feedback": "feedback",
    "/api/events": "analytics",
}

# Valid event types that can be recorded.
VALID_EVENTS = frozenset({
    "session_created",
    "message_sent",
    "simulation_completed",
    "debrief_viewed",
    "playbook_generated",
    "offer_analyzed",
    "challenge_completed",
    "feedback_submitted",
    "feature_used",
})


class AnalyticsTracker:
    """Append-only event logger backed by a JSONL file.

    Thread-safe writes via a lock. Reads parse the full file each time --
    fine for <100k events. For larger volumes, swap to SQLite.
    """

    # Stats cache: avoids full JSONL scan on every admin dashboard hit.
    # 60-second TTL is sufficient for operational visibility.
    _STATS_CACHE_TTL: float = 60.0

    def __init__(self, file_path: str | None = None):
        self._path = Path(file_path) if file_path else _DATA_DIR / "events.jsonl"
        self._lock = threading.Lock()
        self._stats_cache: dict | None = None
        self._stats_cache_ts: float = 0.0
        self._ensure_dir()

    # -- Core API -------------------------------------------------------------

    def track(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Append a single event with an automatic UTC timestamp.

        Args:
            event_type: One of the VALID_EVENTS strings.
            data: Arbitrary properties dict (no PII).
        """
        record = {
            "event": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "properties": data or {},
        }
        self._append(record)

    def track_feature(self, feature_name: str, extra: dict[str, Any] | None = None) -> None:
        """Convenience wrapper: emit a ``feature_used`` event."""
        props = {"feature_name": feature_name}
        if extra:
            props.update(extra)
        self.track("feature_used", props)

    # -- Aggregation ----------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Compute aggregate statistics for the admin dashboard.

        Results are cached for _STATS_CACHE_TTL seconds (60 s) to avoid
        a full JSONL scan on every admin dashboard hit. Under load this
        reduces read lock contention and keeps the admin endpoint fast
        even when the events file has grown large.

        Returns a dict with:
            total_sessions, completion_rate, average_score,
            feature_usage, feature_usage_order, scenario_popularity,
            score_distribution, daily_active_sessions
        """
        now = time.monotonic()
        if (
            self._stats_cache is not None
            and (now - self._stats_cache_ts) < self._STATS_CACHE_TTL
        ):
            return self._stats_cache

        result = self._compute_stats()
        self._stats_cache = result
        self._stats_cache_ts = now
        return result

    def _compute_stats(self) -> dict[str, Any]:
        """Full JSONL scan — called by get_stats() at most once per TTL window."""
        events = self._read_all()

        # -- basic counts -----------------------------------------------------
        sessions = [e for e in events if e["event"] == "session_created"]
        completions = [e for e in events if e["event"] == "simulation_completed"]
        messages = [e for e in events if e["event"] == "message_sent"]

        total_sessions = len(sessions)
        total_completed = len(completions)
        completion_rate = (
            round(total_completed / total_sessions * 100, 1)
            if total_sessions > 0
            else 0.0
        )

        scores = [
            e["properties"]["overall_score"]
            for e in completions
            if "overall_score" in e.get("properties", {})
        ]
        average_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        # -- feature usage (THE key metric) -----------------------------------
        feature_counts: Counter[str] = Counter()
        for e in events:
            if e["event"] == "feature_used":
                fname = e.get("properties", {}).get("feature_name", "unknown")
                feature_counts[fname] += 1
            else:
                # Also count major event types as implicit feature usage
                implicit = _event_to_feature(e["event"])
                if implicit:
                    feature_counts[implicit] += 1

        feature_usage = dict(feature_counts)
        feature_usage_order = [name for name, _ in feature_counts.most_common()]

        # -- scenario popularity ----------------------------------------------
        scenario_counts: Counter[str] = Counter()
        for e in sessions:
            stype = e.get("properties", {}).get("scenario_type", "unknown")
            scenario_counts[stype] += 1

        # -- score distribution (buckets of 10) -------------------------------
        score_dist: dict[str, int] = defaultdict(int)
        for s in scores:
            bucket = f"{(s // 10) * 10}-{(s // 10) * 10 + 9}"
            score_dist[bucket] += 1

        # -- daily active sessions (last 30 days) -----------------------------
        daily: Counter[str] = Counter()
        for e in sessions:
            day = e["timestamp"][:10]  # YYYY-MM-DD
            daily[day] += 1

        today = datetime.now(timezone.utc).date()
        daily_active = []
        for i in range(30):
            d = (today - timedelta(days=29 - i)).isoformat()
            daily_active.append({"date": d, "sessions": daily.get(d, 0)})

        return {
            "total_sessions": total_sessions,
            "total_completed": total_completed,
            "total_messages": len(messages),
            "completion_rate": completion_rate,
            "average_score": average_score,
            "feature_usage": feature_usage,
            "feature_usage_order": feature_usage_order,
            "scenario_popularity": dict(scenario_counts),
            "score_distribution": dict(score_dist),
            "daily_active_sessions": daily_active,
        }

    def get_events(self, event_type: str | None = None, limit: int = 200) -> list[dict]:
        """Return raw events, optionally filtered by type, most recent first."""
        events = self._read_all()
        if event_type:
            events = [e for e in events if e["event"] == event_type]
        return list(reversed(events[-limit:]))

    # -- Internal helpers -----------------------------------------------------

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
                logger.warning("Analytics write failed for %s", self._path, exc_info=True)

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
            logger.warning("Analytics read failed for %s", self._path, exc_info=True)
        return records


# -- Module-level helpers -----------------------------------------------------

def _event_to_feature(event_type: str) -> str | None:
    """Map core event types to feature names for implicit tracking."""
    mapping = {
        "session_created": "simulation",
        "simulation_completed": "debrief",
        "debrief_viewed": "debrief",
        "playbook_generated": "playbook",
        "offer_analyzed": "offer_analyzer",
        "challenge_completed": "daily_challenge",
        "feedback_submitted": "feedback",
    }
    return mapping.get(event_type)


# -- Singleton for easy import ------------------------------------------------

_tracker: AnalyticsTracker | None = None


def get_tracker() -> AnalyticsTracker:
    """Return (or create) the module-level AnalyticsTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = AnalyticsTracker()
    return _tracker
