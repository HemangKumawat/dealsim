"""
Error monitoring and health system for DealSim.

Provides:
- Request logging middleware (access.jsonl, daily rotation)
- Error tracking middleware (errors.jsonl, last-100 in memory)
- Enhanced /api/health endpoint data (uptime, request count, error rate, disk usage)

Unit convention: all timestamps are ISO 8601 UTC strings.
No external dependencies — stdlib + asyncio only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("dealsim.monitoring")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR = Path(os.environ.get("DEALSIM_DATA_DIR", "data"))
_LOGS_DIR = _DATA_DIR / "logs"
_ACCESS_LOG = _LOGS_DIR / "access.jsonl"
_ERROR_LOG = _LOGS_DIR / "errors.jsonl"

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

_start_time: float = time.time()
_total_requests: int = 0
_recent_errors: deque[dict[str, Any]] = deque(maxlen=100)

# Per-minute buckets for error-rate calculation: {minute_epoch: count}
# Keyed by integer floor(unix_timestamp / 60), kept for 10 minutes max.
_error_buckets: dict[int, int] = {}

# asyncio lock for file writes (used inside async middleware)
_access_lock: asyncio.Lock | None = None
_error_lock: asyncio.Lock | None = None


def _get_access_lock() -> asyncio.Lock:
    global _access_lock
    if _access_lock is None:
        _access_lock = asyncio.Lock()
    return _access_lock


def _get_error_lock() -> asyncio.Lock:
    global _error_lock
    if _error_lock is None:
        _error_lock = asyncio.Lock()
    return _error_lock


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def _ensure_logs_dir() -> None:
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _rotate_daily(path: Path) -> None:
    """If the log file is from a previous calendar day, rename it.

    New name format: access.2025-01-15.jsonl (or errors.2025-01-15.jsonl).
    Caller must hold the relevant asyncio lock.
    """
    if not path.exists():
        return
    try:
        mtime = path.stat().st_mtime
        file_date = datetime.fromtimestamp(mtime, tz=timezone.utc).date()
        today = datetime.now(timezone.utc).date()
        if file_date < today:
            stem = path.stem        # e.g. "access"
            suffix = path.suffix    # ".jsonl"
            rotated = path.parent / f"{stem}.{file_date.isoformat()}{suffix}"
            # If the rotated target already exists, append a counter to avoid
            # overwriting (edge case: two rotations on same day).
            if rotated.exists():
                counter = 1
                while rotated.exists():
                    rotated = path.parent / f"{stem}.{file_date.isoformat()}.{counter}{suffix}"
                    counter += 1
            os.replace(str(path), str(rotated))
    except OSError:
        pass


async def _append_json(path: Path, record: dict[str, Any], lock: asyncio.Lock) -> None:
    """Rotate if needed, then append one JSON line — under async lock."""
    async with lock:
        _rotate_daily(path)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except OSError:
            logger.warning("Failed to write to %s", path, exc_info=True)


# ---------------------------------------------------------------------------
# Error bucket helpers
# ---------------------------------------------------------------------------

def _record_error_in_bucket() -> None:
    """Increment the current one-minute bucket and evict stale buckets."""
    now = time.time()
    bucket = int(now // 60)
    _error_buckets[bucket] = _error_buckets.get(bucket, 0) + 1
    # Evict buckets older than 10 minutes
    cutoff = bucket - 10
    stale = [k for k in _error_buckets if k < cutoff]
    for k in stale:
        del _error_buckets[k]


def _error_rate_last_5min() -> float:
    """Return errors per minute averaged over the last 5 minutes."""
    now = time.time()
    current_bucket = int(now // 60)
    # Buckets for t-5 through t-1 (exclude the still-filling current bucket)
    total = sum(
        _error_buckets.get(current_bucket - i, 0)
        for i in range(1, 6)
    )
    return round(total / 5.0, 2)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request to data/logs/access.jsonl.

    Fields: timestamp, method, path, status_code, response_time_ms
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        _ensure_logs_dir()

    async def dispatch(self, request: Request, call_next):
        global _total_requests
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        _total_requests += 1

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "response_time_ms": elapsed_ms,
        }

        # Fire-and-forget disk write — does not block the response
        asyncio.create_task(
            _append_json(_ACCESS_LOG, record, _get_access_lock())
        )

        return response


# ---------------------------------------------------------------------------
# Error tracking middleware
# ---------------------------------------------------------------------------

class ErrorTrackingMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions, log them, and return a safe 500 response.

    Also keeps the last 100 errors in the _recent_errors deque.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        _ensure_logs_dir()

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            tb = traceback.format_exc()
            record: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": request.url.path,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "traceback": tb,
            }
            _recent_errors.append(record)
            _record_error_in_bucket()

            asyncio.create_task(
                _append_json(_ERROR_LOG, record, _get_error_lock())
            )

            logger.error(
                "Unhandled exception on %s %s: %s\n%s",
                request.method,
                request.url.path,
                exc,
                tb,
            )

            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )


# ---------------------------------------------------------------------------
# Disk usage helper
# ---------------------------------------------------------------------------

def _data_dir_size_mb() -> float:
    """Return total size of the data/ directory in MB, or -1 on error."""
    try:
        total = sum(
            f.stat().st_size
            for f in _DATA_DIR.rglob("*")
            if f.is_file()
        )
        return round(total / (1024 * 1024), 3)
    except OSError:
        return -1.0


# ---------------------------------------------------------------------------
# Public API: health data
# ---------------------------------------------------------------------------

def get_health_data(active_sessions: int = 0) -> dict[str, Any]:
    """Return the full health payload for /api/health.

    Args:
        active_sessions: Current count of in-memory sessions (pass from app).
    """
    uptime_seconds = round(time.time() - _start_time, 1)

    last_error_ts: str | None = None
    if _recent_errors:
        last_error_ts = _recent_errors[-1]["timestamp"]

    # Overall status: degraded if error rate > 1/min, unhealthy if > 5/min
    error_rate = _error_rate_last_5min()
    if error_rate > 5.0:
        status = "unhealthy"
    elif error_rate > 1.0:
        status = "degraded"
    else:
        status = "healthy"

    return {
        "status": status,
        "uptime_seconds": uptime_seconds,
        "total_requests": _total_requests,
        "error_rate_per_min": error_rate,
        "active_sessions": active_sessions,
        "data_dir_size_mb": _data_dir_size_mb(),
        "last_error_timestamp": last_error_ts,
    }
