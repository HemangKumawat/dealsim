"""
Tests for the token-bucket rate limiter (rate_limiter.py).

Unit tests exercise the core logic directly against the module functions;
integration tests confirm that the FastAPI middleware wires up correctly and
returns HTTP 429 with the expected headers.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import dealsim_mvp.rate_limiter as rl
from dealsim_mvp.app import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset():
    """Clear all bucket state between tests."""
    rl._BUCKETS.clear()
    # Reset the cleanup-started flag so each test gets a clean slate.
    rl.RateLimitMiddleware._cleanup_started = False


@pytest.fixture(autouse=True)
def clean_buckets():
    _reset()
    yield
    _reset()


# ---------------------------------------------------------------------------
# Unit: _resolve_config
# ---------------------------------------------------------------------------

class TestResolveConfig:
    def test_session_creation(self):
        cfg = rl._resolve_config("/api/sessions")
        assert cfg.name == "session_creation"
        assert cfg.capacity == 5

    def test_chat_message(self):
        cfg = rl._resolve_config("/api/sessions/abc123/message")
        assert cfg.name == "chat"
        assert cfg.capacity == 30

    def test_scoring_complete(self):
        cfg = rl._resolve_config("/api/sessions/abc123/complete")
        assert cfg.name == "scoring"
        assert cfg.capacity == 10

    def test_scoring_debrief(self):
        cfg = rl._resolve_config("/api/sessions/abc123/debrief")
        assert cfg.name == "scoring"

    def test_scoring_playbook(self):
        cfg = rl._resolve_config("/api/sessions/abc123/playbook")
        assert cfg.name == "scoring"

    def test_feedback(self):
        cfg = rl._resolve_config("/api/feedback")
        assert cfg.name == "feedback"
        assert cfg.capacity == 3

    def test_events(self):
        cfg = rl._resolve_config("/api/events")
        assert cfg.name == "feedback"

    def test_health(self):
        cfg = rl._resolve_config("/health")
        assert cfg.capacity == 0  # unlimited sentinel

    def test_api_health(self):
        cfg = rl._resolve_config("/api/health")
        assert cfg.capacity == 0

    def test_unknown_path_uses_default(self):
        cfg = rl._resolve_config("/api/scenarios")
        assert cfg.name == "default"
        assert cfg.capacity == 100


# ---------------------------------------------------------------------------
# Unit: check() — allow / reject behaviour
# ---------------------------------------------------------------------------

class TestCheck:
    def test_allows_within_limit(self):
        for _ in range(5):
            allowed, retry = rl.check("1.2.3.4", "/api/sessions")
            assert allowed is True
            assert retry == 0

    def test_rejects_on_sixth_session_creation(self):
        ip = "1.2.3.4"
        for _ in range(5):
            rl.check(ip, "/api/sessions")
        allowed, retry = rl.check(ip, "/api/sessions")
        assert allowed is False
        assert retry > 0

    def test_health_never_rejected(self):
        ip = "1.2.3.4"
        for _ in range(1000):
            allowed, _ = rl.check(ip, "/health")
            assert allowed is True

    def test_different_ips_have_independent_buckets(self):
        for _ in range(5):
            rl.check("10.0.0.1", "/api/sessions")
        # IP .2 has not been used yet — full bucket
        allowed, _ = rl.check("10.0.0.2", "/api/sessions")
        assert allowed is True

    def test_different_paths_have_independent_buckets(self):
        ip = "1.2.3.4"
        # Exhaust session creation bucket
        for _ in range(5):
            rl.check(ip, "/api/sessions")
        allowed, _ = rl.check(ip, "/api/sessions")
        assert allowed is False
        # Chat bucket for the same IP is untouched
        allowed_chat, _ = rl.check(ip, "/api/sessions/x/message")
        assert allowed_chat is True

    def test_tokens_refill_over_time(self):
        ip = "1.2.3.4"
        # Exhaust feedback bucket (capacity=3)
        for _ in range(3):
            rl.check(ip, "/api/feedback")
        allowed, _ = rl.check(ip, "/api/feedback")
        assert allowed is False

        # Simulate 25 seconds passing — refill_rate = 3/60 = 0.05 t/s
        # 25s * 0.05 = 1.25 tokens — bucket should have >=1 token again.
        cfg = rl._resolve_config("/api/feedback")
        bucket = rl._BUCKETS[("1.2.3.4", "feedback")]
        bucket.last_refill -= 25.0  # rewind the clock

        allowed_after, _ = rl.check(ip, "/api/feedback")
        assert allowed_after is True

    def test_retry_after_is_positive_on_rejection(self):
        ip = "5.5.5.5"
        for _ in range(3):
            rl.check(ip, "/api/feedback")
        _, retry = rl.check(ip, "/api/feedback")
        assert retry >= 1


# ---------------------------------------------------------------------------
# Unit: retry_after calculation
# ---------------------------------------------------------------------------

class TestRetryAfter:
    def test_returns_ceiling_of_wait_time(self):
        cfg = rl.BucketConfig("test", capacity=10, window_seconds=60.0)
        now = time.monotonic()
        bucket = rl._Bucket(tokens=0.0, last_refill=now, last_access=now)
        # refill_rate = 10/60 ≈ 0.167 t/s; deficit = 1 token → wait ≈ 6s
        retry = bucket.retry_after(cfg, now)
        assert retry == 6


# ---------------------------------------------------------------------------
# Unit: eviction
# ---------------------------------------------------------------------------

class TestEviction:
    def test_evicts_idle_buckets(self):
        rl.check("2.2.2.2", "/api/feedback")
        assert len(rl._BUCKETS) == 1

        # Make the bucket appear idle for longer than _EVICT_AFTER_IDLE
        for b in rl._BUCKETS.values():
            b.last_access -= rl._EVICT_AFTER_IDLE + 1

        rl._evict_idle()
        assert len(rl._BUCKETS) == 0

    def test_does_not_evict_recently_used(self):
        rl.check("3.3.3.3", "/api/feedback")
        rl._evict_idle()
        assert len(rl._BUCKETS) == 1


# ---------------------------------------------------------------------------
# Integration: middleware via TestClient
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


class TestRateLimitMiddlewareIntegration:
    def test_health_never_rate_limited(self, api_client):
        for _ in range(50):
            r = api_client.get("/health")
            assert r.status_code == 200

    def test_429_on_feedback_after_limit(self, api_client):
        """The feedback endpoint allows 3/min — the 4th should be 429."""
        payload = {
            "session_id": "00000000-0000-4000-8000-000000000001",
            "rating": 4,
        }
        # First three must pass (or fail for other reasons — not 429)
        for i in range(3):
            r = api_client.post("/api/feedback", json=payload,
                                headers={"X-Forwarded-For": "99.1.2.3"})
            assert r.status_code != 429, f"request {i+1} was unexpectedly rate-limited"

        # Fourth must be 429
        r = api_client.post("/api/feedback", json=payload,
                            headers={"X-Forwarded-For": "99.1.2.3"})
        assert r.status_code == 429
        body = r.json()
        assert "retry_after_seconds" in body
        assert int(r.headers["Retry-After"]) >= 1

    def test_429_response_body_fields(self, api_client):
        payload = {
            "session_id": "00000000-0000-4000-8000-000000000001",
            "rating": 4,
        }
        for _ in range(3):
            api_client.post("/api/feedback", json=payload,
                            headers={"X-Forwarded-For": "77.7.7.7"})
        r = api_client.post("/api/feedback", json=payload,
                            headers={"X-Forwarded-For": "77.7.7.7"})
        assert r.status_code == 429
        body = r.json()
        assert "error" in body
        assert body.get("code") == "RATE_LIMITED"
        assert "retry_after_seconds" in body
        assert "Retry-After" in r.headers
        assert "X-Request-ID" in r.headers

    def test_different_ips_not_cross_limited(self):
        # Test via check() directly — the HTTP layer ignores X-Forwarded-For
        # unless DEALSIM_TRUSTED_PROXY is configured (correct security posture).
        # Exhaust IP A
        for _ in range(3):
            rl.check("11.11.11.11", "/api/feedback")
        allowed_a, _ = rl.check("11.11.11.11", "/api/feedback")
        assert allowed_a is False

        # IP B has an independent bucket — still at full capacity
        allowed_b, _ = rl.check("22.22.22.22", "/api/feedback")
        assert allowed_b is True
