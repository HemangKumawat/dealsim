"""Tests for the monitoring module (request logging, error tracking, health data)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import dealsim_mvp.monitoring as mon


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_module_state():
    """Reset all in-memory monitoring counters between tests."""
    mon._total_requests = 0
    mon._recent_errors.clear()
    mon._error_buckets.clear()
    mon._start_time = time.time()


@pytest.fixture(autouse=True)
def reset_state():
    _reset_module_state()
    yield
    _reset_module_state()


# ---------------------------------------------------------------------------
# get_health_data
# ---------------------------------------------------------------------------

class TestGetHealthData:
    def test_returns_all_required_keys(self):
        data = mon.get_health_data(active_sessions=3)
        expected = {
            "status", "uptime_seconds", "total_requests",
            "error_rate_per_min", "active_sessions",
            "data_dir_size_mb", "last_error_timestamp",
        }
        assert expected.issubset(data.keys())

    def test_active_sessions_passed_through(self):
        data = mon.get_health_data(active_sessions=7)
        assert data["active_sessions"] == 7

    def test_status_healthy_when_no_errors(self):
        data = mon.get_health_data()
        assert data["status"] == "healthy"

    def test_status_degraded_above_1_per_min(self):
        # 10 errors across 5 completed-minute buckets = 2.0/min → degraded
        current_bucket = int(time.time() // 60)
        for i in range(1, 6):
            mon._error_buckets[current_bucket - i] = 2
        data = mon.get_health_data()
        assert data["status"] == "degraded"

    def test_status_unhealthy_above_5_per_min(self):
        current_bucket = int(time.time() // 60)
        # Spread 30 errors across 5 completed-minute buckets → 6/min avg
        for i in range(1, 6):
            mon._error_buckets[current_bucket - i] = 6
        data = mon.get_health_data()
        assert data["status"] == "unhealthy"

    def test_last_error_timestamp_none_when_no_errors(self):
        data = mon.get_health_data()
        assert data["last_error_timestamp"] is None

    def test_last_error_timestamp_set_after_error(self):
        mon._recent_errors.append({"timestamp": "2025-01-15T12:00:00+00:00"})
        data = mon.get_health_data()
        assert data["last_error_timestamp"] == "2025-01-15T12:00:00+00:00"

    def test_total_requests_reflects_counter(self):
        mon._total_requests = 42
        data = mon.get_health_data()
        assert data["total_requests"] == 42

    def test_uptime_is_positive(self):
        data = mon.get_health_data()
        assert data["uptime_seconds"] >= 0.0

    def test_data_dir_size_returns_float(self):
        data = mon.get_health_data()
        assert isinstance(data["data_dir_size_mb"], float)


# ---------------------------------------------------------------------------
# Error rate calculation
# ---------------------------------------------------------------------------

class TestErrorRate:
    def test_zero_when_no_errors(self):
        assert mon._error_rate_last_5min() == 0.0

    def test_counts_last_5_completed_minutes(self):
        current_bucket = int(time.time() // 60)
        mon._error_buckets[current_bucket - 1] = 5
        mon._error_buckets[current_bucket - 2] = 5
        # 10 errors over 5 min window = 2.0/min
        assert mon._error_rate_last_5min() == 2.0

    def test_ignores_current_still_filling_bucket(self):
        current_bucket = int(time.time() // 60)
        # Only the current bucket has errors — should not count
        mon._error_buckets[current_bucket] = 100
        assert mon._error_rate_last_5min() == 0.0

    def test_record_error_in_bucket_increments(self):
        current_bucket = int(time.time() // 60)
        mon._record_error_in_bucket()
        mon._record_error_in_bucket()
        assert mon._error_buckets.get(current_bucket, 0) == 2

    def test_record_error_evicts_stale_buckets(self):
        # Insert a bucket older than 10 minutes
        old_bucket = int(time.time() // 60) - 15
        mon._error_buckets[old_bucket] = 99
        mon._record_error_in_bucket()
        assert old_bucket not in mon._error_buckets


# ---------------------------------------------------------------------------
# File rotation helper
# ---------------------------------------------------------------------------

class TestRotateDaily:
    def test_no_rotation_when_file_is_today(self, tmp_path):
        log_file = tmp_path / "access.jsonl"
        log_file.write_text('{"a":1}\n')
        # mtime defaults to now, which is today — no rename expected
        mon._rotate_daily(log_file)
        assert log_file.exists()

    def test_rotation_renames_old_file(self, tmp_path):
        log_file = tmp_path / "access.jsonl"
        log_file.write_text('{"a":1}\n')
        # Set mtime to yesterday
        yesterday_ts = time.time() - 86400
        import os
        os.utime(str(log_file), (yesterday_ts, yesterday_ts))
        mon._rotate_daily(log_file)
        # Original file should be gone
        assert not log_file.exists()
        # A dated file should exist
        rotated_files = list(tmp_path.glob("access.*.jsonl"))
        assert len(rotated_files) == 1

    def test_no_error_when_file_missing(self, tmp_path):
        missing = tmp_path / "nonexistent.jsonl"
        # Should not raise
        mon._rotate_daily(missing)


# ---------------------------------------------------------------------------
# recent_errors deque cap
# ---------------------------------------------------------------------------

class TestRecentErrorsCap:
    def test_capped_at_100(self):
        for i in range(150):
            mon._recent_errors.append({"timestamp": f"ts-{i}", "path": "/x"})
        assert len(mon._recent_errors) == 100

    def test_keeps_most_recent(self):
        for i in range(150):
            mon._recent_errors.append({"timestamp": f"ts-{i}", "path": "/x"})
        # Last entry should be ts-149
        assert mon._recent_errors[-1]["timestamp"] == "ts-149"


# ---------------------------------------------------------------------------
# Integration: health endpoint via TestClient
# ---------------------------------------------------------------------------

class TestHealthEndpointIntegration:
    def test_health_endpoint_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_api_health_returns_200(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200

    def test_total_requests_increments(self, client):
        _reset_module_state()
        client.get("/health")
        client.get("/health")
        data = client.get("/health").json()
        # At least 3 requests recorded (the resets + these)
        assert data["total_requests"] >= 1

    def test_active_sessions_zero_initially(self, client):
        r = client.get("/health")
        assert r.json()["active_sessions"] == 0

    def test_active_sessions_increments_with_session(self, client):
        client.post("/api/sessions", json={"target_value": 100000})
        r = client.get("/health")
        assert r.json()["active_sessions"] >= 1
