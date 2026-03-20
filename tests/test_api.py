"""Tests for FastAPI endpoints."""

import pytest


class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in {"healthy", "degraded", "unhealthy"}
        assert "version" in data

    def test_health_enhanced_fields(self, client):
        r = client.get("/health")
        data = r.json()
        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert "error_rate_per_min" in data
        assert "active_sessions" in data
        assert "data_dir_size_mb" in data
        assert "last_error_timestamp" in data

    def test_api_health_alias(self, client):
        """GET /api/health returns the same payload as /health."""
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in {"healthy", "degraded", "unhealthy"}
        assert "uptime_seconds" in data


class TestCreateSession:
    def test_creates_session(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 120000,
            "difficulty": "medium",
        })
        assert r.status_code == 201
        data = r.json()
        assert "session_id" in data
        assert "opponent_name" in data
        assert "opening_message" in data
        assert len(data["opening_message"]) > 0

    def test_returns_opponent_name_and_role(self, client):
        r = client.post("/api/sessions", json={"target_value": 100000})
        data = r.json()
        assert isinstance(data["opponent_name"], str)
        assert isinstance(data["opponent_role"], str)

    def test_returns_opening_offer(self, client):
        r = client.post("/api/sessions", json={"target_value": 100000})
        data = r.json()
        assert data["opening_offer"] is not None
        assert data["opening_offer"] > 0

    def test_default_values(self, client):
        # target_value is required; scenario_type and difficulty have defaults
        r = client.post("/api/sessions", json={"target_value": 100000})
        assert r.status_code == 201


class TestSendMessage:
    def test_returns_opponent_response(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]

        r2 = client.post(f"/api/sessions/{sid}/message", json={
            "message": "I'm looking for $130,000",
        })
        assert r2.status_code == 200
        data = r2.json()
        assert "opponent_response" in data
        assert len(data["opponent_response"]) > 0
        assert "round_number" in data
        assert "session_status" in data

    def test_400_for_invalid_session_id_format(self, client):
        r = client.post("/api/sessions/fake-id/message", json={
            "message": "hello",
        })
        assert r.status_code == 400

    def test_404_for_nonexistent_session(self, client):
        r = client.post("/api/sessions/00000000-0000-4000-a000-000000000000/message", json={
            "message": "hello",
        })
        assert r.status_code == 404

    def test_409_for_completed_session(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]
        # Send a message, then complete
        client.post(f"/api/sessions/{sid}/message", json={"message": "I want $130K"})
        client.post(f"/api/sessions/{sid}/complete")
        # Try to negotiate again
        r = client.post(f"/api/sessions/{sid}/message", json={"message": "hello"})
        assert r.status_code == 409

    def test_empty_message_rejected(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]
        r = client.post(f"/api/sessions/{sid}/message", json={"message": ""})
        assert r.status_code == 422  # Pydantic validation (min_length=1)


class TestCompleteSession:
    def test_returns_scorecard(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]
        client.post(f"/api/sessions/{sid}/message", json={"message": "I want $130K"})

        r = client.post(f"/api/sessions/{sid}/complete")
        assert r.status_code == 200
        data = r.json()
        assert "overall_score" in data
        assert "dimensions" in data
        assert len(data["dimensions"]) == 6
        assert "top_tips" in data
        assert "outcome" in data
        assert "opponent_name" in data

    def test_dimensions_have_required_fields(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]
        client.post(f"/api/sessions/{sid}/message", json={"message": "I want $130K"})

        r = client.post(f"/api/sessions/{sid}/complete")
        for dim in r.json()["dimensions"]:
            assert "name" in dim
            assert "score" in dim
            assert "weight" in dim
            assert "explanation" in dim
            assert "tips" in dim

    def test_400_for_invalid_session_id_format(self, client):
        r = client.post("/api/sessions/fake-id/complete")
        assert r.status_code == 400

    def test_404_for_nonexistent_session(self, client):
        r = client.post("/api/sessions/00000000-0000-4000-a000-000000000000/complete")
        assert r.status_code == 404


class TestGetSession:
    """GET /api/sessions/{id} -- returns session state."""

    def test_400_for_invalid_session_id_format(self, client):
        r = client.get("/api/sessions/fake-id")
        assert r.status_code == 400

    def test_404_for_nonexistent_session(self, client):
        r = client.get("/api/sessions/00000000-0000-4000-a000-000000000000")
        assert r.status_code == 404

    def test_returns_session_state(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]
        r = client.get(f"/api/sessions/{sid}")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == sid
        assert "transcript" in data
        assert isinstance(data["transcript"], list)
        assert data["round_number"] >= 0


class TestIndexPage:
    """GET / should return HTML or JSON fallback."""

    def test_index_endpoint_exists(self, client):
        r = client.get("/")
        # May be 200 with HTML or JSON fallback depending on static dir presence
        assert r.status_code == 200


class TestFeedback:
    """POST /api/feedback -- submit user feedback."""

    def test_submit_feedback(self, client):
        # Create a session first to get a valid session_id
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]

        r = client.post("/api/feedback", json={
            "session_id": sid,
            "rating": 4,
            "comment": "Great tool!",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestInputValidation:
    """Pydantic validators on scenario_type, difficulty, message, and feedback."""

    def test_invalid_scenario_type_rejected(self, client):
        r = client.post("/api/sessions", json={
            "target_value": 100000,
            "scenario_type": "underwater_basketweaving",
        })
        assert r.status_code == 422

    def test_invalid_difficulty_rejected(self, client):
        r = client.post("/api/sessions", json={
            "target_value": 100000,
            "difficulty": "extreme",
        })
        assert r.status_code == 422

    def test_valid_scenario_types_accepted(self, client):
        for stype in ("salary", "freelance", "rent", "raise", "vendor"):
            r = client.post("/api/sessions", json={
                "target_value": 50000,
                "scenario_type": stype,
            })
            assert r.status_code == 201, f"Expected 201 for scenario_type={stype!r}, got {r.status_code}"

    def test_valid_difficulties_accepted(self, client):
        for diff in ("easy", "medium", "hard"):
            r = client.post("/api/sessions", json={
                "target_value": 50000,
                "difficulty": diff,
            })
            assert r.status_code == 201, f"Expected 201 for difficulty={diff!r}, got {r.status_code}"

    def test_message_too_long_rejected(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]
        r = client.post(f"/api/sessions/{sid}/message", json={"message": "x" * 2001})
        assert r.status_code == 422

    def test_feedback_rating_below_1_rejected(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]
        r = client.post("/api/feedback", json={"session_id": sid, "rating": 0})
        assert r.status_code == 422

    def test_feedback_rating_above_5_rejected(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]
        r = client.post("/api/feedback", json={"session_id": sid, "rating": 6})
        assert r.status_code == 422

    def test_feedback_comment_too_long_rejected(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        sid = r1.json()["session_id"]
        r = client.post("/api/feedback", json={
            "session_id": sid,
            "rating": 3,
            "comment": "x" * 1001,
        })
        assert r.status_code == 422

    def test_zero_target_value_rejected(self, client):
        r = client.post("/api/sessions", json={"target_value": 0})
        assert r.status_code == 422

    def test_negative_target_value_rejected(self, client):
        r = client.post("/api/sessions", json={"target_value": -5000})
        assert r.status_code == 422


class TestRequestID:
    """X-Request-ID header returned on every response."""

    def test_health_returns_request_id(self, client):
        r = client.get("/health")
        assert "x-request-id" in r.headers

    def test_successful_response_returns_request_id(self, client):
        r = client.post("/api/sessions", json={"target_value": 100000})
        assert r.status_code == 201
        assert "x-request-id" in r.headers

    def test_request_id_is_unique_per_request(self, client):
        r1 = client.post("/api/sessions", json={"target_value": 100000})
        r2 = client.post("/api/sessions", json={"target_value": 100000})
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]

    def test_error_response_includes_request_id(self, client):
        r = client.post("/api/sessions/fake-id/message", json={"message": "hello"})
        assert r.status_code == 400
        # FastAPI wraps HTTPException.detail under the "detail" key
        detail = r.json()["detail"]
        assert detail["error"] == "Invalid session ID format"
        assert detail["code"] == "INVALID_SESSION_ID"
        assert "request_id" in detail

    def test_404_uses_consistent_error_shape(self, client):
        r = client.get("/api/sessions/00000000-0000-4000-a000-000000000000")
        assert r.status_code == 404
        detail = r.json()["detail"]
        assert "error" in detail
        assert detail["code"] == "SESSION_NOT_FOUND"
        assert "request_id" in detail
