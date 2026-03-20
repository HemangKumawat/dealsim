"""
Application-level rate limiter for DealSim.

Implements a token bucket algorithm per IP address with different limits for
different endpoint groups. Designed as a FastAPI middleware that sits above
nginx (which handles connection-level limiting externally).

Token Bucket Mechanics
----------------------
Each IP has a bucket per endpoint group. The bucket holds up to `capacity`
tokens. Tokens refill at a constant rate (capacity / window_seconds per second).
A request consumes one token. If the bucket is empty the request is rejected
with HTTP 429 and a Retry-After header.

Endpoint Groups (requests per minute per IP)
--------------------------------------------
- session_creation : 5   (POST /api/sessions)
- chat             : 30  (POST /api/sessions/{id}/message)
- scoring          : 10  (POST /api/sessions/{id}/complete, GET /api/sessions/{id}/debrief,
                          GET /api/sessions/{id}/playbook)
- feedback         : 3   (POST /api/feedback, POST /api/events)
- health           : unlimited  (/health, /api/health)
- default          : 100 (everything else)

Cleanup
-------
A background asyncio task runs every 5 minutes and evicts buckets that have
not been accessed for 10+ minutes, keeping memory bounded under sustained load.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import ClassVar

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("dealsim.rate_limiter")

# ---------------------------------------------------------------------------
# Endpoint group configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BucketConfig:
    """Rate limit parameters for one endpoint group."""
    name: str
    # Maximum tokens in the bucket (= burst ceiling = requests per window).
    capacity: int
    # Length of the refill window in seconds.
    window_seconds: float = 60.0

    @property
    def refill_rate(self) -> float:
        """Tokens per second added to the bucket."""
        return self.capacity / self.window_seconds


# Sentinel: no limit.
_UNLIMITED = BucketConfig(name="health", capacity=0, window_seconds=60.0)

_GROUPS: list[tuple[re.Pattern[str], str, BucketConfig]] = [
    # Health — unlimited
    (re.compile(r"^/(api/)?health$"), "health", _UNLIMITED),
    # Session creation
    (re.compile(r"^/api/sessions$"), "session_creation",
     BucketConfig("session_creation", capacity=5)),
    # Chat messages
    (re.compile(r"^/api/sessions/[^/]+/message$"), "chat",
     BucketConfig("chat", capacity=30)),
    # Scoring / debrief / playbook
    (re.compile(r"^/api/sessions/[^/]+/(complete|debrief|playbook)$"), "scoring",
     BucketConfig("scoring", capacity=10)),
    # Feedback and event tracking
    (re.compile(r"^/api/(feedback|events)$"), "feedback",
     BucketConfig("feedback", capacity=3)),
]

_DEFAULT_CONFIG = BucketConfig("default", capacity=100)


def _resolve_config(path: str) -> BucketConfig:
    """Return the BucketConfig for a given URL path."""
    for pattern, _name, cfg in _GROUPS:
        if pattern.match(path):
            return cfg
    return _DEFAULT_CONFIG


# ---------------------------------------------------------------------------
# Token bucket state
# ---------------------------------------------------------------------------

@dataclass
class _Bucket:
    """Mutable token bucket for one (ip, group) pair."""
    tokens: float
    last_refill: float  # epoch seconds
    last_access: float  # epoch seconds — used for eviction

    def consume(self, cfg: BucketConfig, now: float) -> bool:
        """
        Refill tokens based on elapsed time, then try to consume one token.

        Returns True if the request is allowed, False if rejected.
        """
        # Unlimited groups always pass.
        if cfg.capacity == 0:
            self.last_access = now
            return True

        elapsed = now - self.last_refill
        self.tokens = min(
            float(cfg.capacity),
            self.tokens + elapsed * cfg.refill_rate,
        )
        self.last_refill = now
        self.last_access = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def retry_after(self, cfg: BucketConfig, now: float) -> int:
        """Seconds until at least one token is available (ceil)."""
        deficit = 1.0 - self.tokens
        return math.ceil(deficit / cfg.refill_rate)


# ---------------------------------------------------------------------------
# Rate limiter store
# ---------------------------------------------------------------------------

# Key: (client_ip, group_name) → _Bucket
_BUCKETS: dict[tuple[str, str], _Bucket] = {}
_STORE_MAX = 50_000   # hard cap on tracked (ip, group) pairs
_EVICT_AFTER_IDLE = 600.0   # 10 minutes
# Protects _BUCKETS against concurrent reads and writes from multiple
# threads (sync route handlers run in a thread pool under uvicorn/gunicorn).
_buckets_lock = threading.Lock()


def _get_or_create(ip: str, cfg: BucketConfig, now: float) -> _Bucket:
    """Caller must hold _buckets_lock."""
    key = (ip, cfg.name)
    bucket = _BUCKETS.get(key)
    if bucket is None:
        # Memory cap: evict the least-recently-used entry before inserting.
        if len(_BUCKETS) >= _STORE_MAX:
            lru_key = min(_BUCKETS, key=lambda k: _BUCKETS[k].last_access)
            del _BUCKETS[lru_key]
        bucket = _Bucket(
            tokens=float(cfg.capacity),
            last_refill=now,
            last_access=now,
        )
        _BUCKETS[key] = bucket
    return bucket


def check(ip: str, path: str) -> tuple[bool, int]:
    """
    Check whether the request from `ip` to `path` is within its rate limit.

    Returns (allowed: bool, retry_after_seconds: int).
    retry_after_seconds is 0 when allowed is True.

    Thread-safe: the entire read-modify-write is performed under _buckets_lock
    so concurrent requests from the same IP cannot both see a full bucket and
    both be granted a token that should not have existed.
    """
    now = time.monotonic()
    cfg = _resolve_config(path)

    # Unlimited config — never creates a bucket.
    if cfg.capacity == 0:
        return True, 0

    with _buckets_lock:
        bucket = _get_or_create(ip, cfg, now)
        allowed = bucket.consume(cfg, now)
        retry = 0 if allowed else bucket.retry_after(cfg, now)
    return allowed, retry


# ---------------------------------------------------------------------------
# Background cleanup task
# ---------------------------------------------------------------------------

_cleanup_task: asyncio.Task | None = None


async def _cleanup_loop(interval: float = 300.0) -> None:
    """Evict idle buckets every `interval` seconds."""
    while True:
        await asyncio.sleep(interval)
        _evict_idle()


def _evict_idle() -> None:
    now = time.monotonic()
    cutoff = now - _EVICT_AFTER_IDLE
    with _buckets_lock:
        stale = [k for k, b in _BUCKETS.items() if b.last_access < cutoff]
        for k in stale:
            del _BUCKETS[k]
        remaining = len(_BUCKETS)
    if stale:
        logger.debug("Rate limiter cleanup: evicted %d idle buckets (%d remaining)",
                     len(stale), remaining)


def start_cleanup_task(interval: float = 300.0) -> None:
    """Start the background cleanup coroutine. Safe to call multiple times."""
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        loop = asyncio.get_event_loop()
        _cleanup_task = loop.create_task(_cleanup_loop(interval))
        logger.debug("Rate limiter cleanup task started (interval=%.0fs)", interval)


def stop_cleanup_task() -> None:
    """Cancel the cleanup task (used in tests)."""
    global _cleanup_task
    if _cleanup_task and not _cleanup_task.done():
        _cleanup_task.cancel()
        _cleanup_task = None


# ---------------------------------------------------------------------------
# FastAPI middleware
# ---------------------------------------------------------------------------

_TRUSTED_PROXY = os.environ.get("DEALSIM_TRUSTED_PROXY", "")


def _extract_ip(request: Request) -> str:
    """Extract the real client IP.

    X-Forwarded-For is a client-controlled header — trusting it
    unconditionally allows any client to forge their IP and bypass rate
    limiting entirely.  We only read it when the direct TCP connection
    comes from a configured trusted proxy (DEALSIM_TRUSTED_PROXY env var).

    When a trusted proxy is configured, we take the *rightmost* entry in
    X-Forwarded-For that was appended by the proxy, not the leftmost
    (which the client can inject).

    Without a configured proxy we use the raw connection address.
    """
    direct_ip = request.client.host if request.client else "unknown"
    if _TRUSTED_PROXY and direct_ip == _TRUSTED_PROXY:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        if forwarded_for:
            # Take the rightmost IP — added by our trusted proxy, not the client.
            candidates = [ip.strip() for ip in forwarded_for.split(",")]
            return candidates[-1] if candidates else direct_ip
    return direct_ip


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Starlette/FastAPI middleware that enforces per-IP token-bucket rate limits.

    Starts the background cleanup task on the first request (i.e., once the
    event loop is running) rather than at import time so it is safe to import
    in test environments.
    """

    _cleanup_started: ClassVar[bool] = False

    async def dispatch(self, request: Request, call_next) -> Response:
        # Lazy-start the cleanup task inside the running event loop.
        if not RateLimitMiddleware._cleanup_started:
            start_cleanup_task()
            RateLimitMiddleware._cleanup_started = True

        path = request.url.path
        ip = _extract_ip(request)
        allowed, retry_after = check(ip, path)

        if not allowed:
            req_id = getattr(request.state, "request_id", "unknown")
            logger.warning(
                "Rate limit exceeded: ip=%s path=%s retry_after=%ds [request_id=%s]",
                ip, path, retry_after, req_id,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded.",
                    "code": "RATE_LIMITED",
                    "retry_after_seconds": retry_after,
                    "request_id": req_id,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-Request-ID": req_id,
                },
            )

        return await call_next(request)
