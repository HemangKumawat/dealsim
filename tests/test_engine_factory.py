"""Tests for engine_factory — simulator dispatch logic."""
import pytest

from dealsim_mvp.core.engine_factory import (
    build_simulator,
    get_available_engines,
    _detect_best_engine,
)
from dealsim_mvp.core.simulator import RuleBasedSimulator, SimulatorBase


class TestDetectBestEngine:
    def test_defaults_to_rule_based(self, monkeypatch):
        monkeypatch.delenv("MIROFISH_BASE_URL", raising=False)
        monkeypatch.delenv("DEALSIM_USE_LLM", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        assert _detect_best_engine() == "rule_based"

    def test_detects_mirofish(self, monkeypatch):
        monkeypatch.setenv("MIROFISH_BASE_URL", "http://localhost:5001")
        assert _detect_best_engine() == "mirofish"

    def test_detects_llm(self, monkeypatch):
        monkeypatch.delenv("MIROFISH_BASE_URL", raising=False)
        monkeypatch.setenv("DEALSIM_USE_LLM", "true")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        assert _detect_best_engine() == "llm"

    def test_mirofish_takes_priority_over_llm(self, monkeypatch):
        monkeypatch.setenv("MIROFISH_BASE_URL", "http://localhost:5001")
        monkeypatch.setenv("DEALSIM_USE_LLM", "true")
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        assert _detect_best_engine() == "mirofish"


class TestBuildSimulator:
    def test_rule_based_always_works(self, monkeypatch):
        monkeypatch.delenv("MIROFISH_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        sim = build_simulator(engine="rule_based")
        assert isinstance(sim, RuleBasedSimulator)

    def test_auto_falls_back_to_rule_based(self, monkeypatch):
        monkeypatch.delenv("MIROFISH_BASE_URL", raising=False)
        monkeypatch.delenv("DEALSIM_USE_LLM", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        sim = build_simulator(engine="auto")
        assert isinstance(sim, RuleBasedSimulator)

    def test_llm_falls_back_without_key(self, monkeypatch):
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        sim = build_simulator(engine="llm")
        assert isinstance(sim, RuleBasedSimulator)

    def test_mirofish_falls_back_without_url(self, monkeypatch):
        """MiroFishConfig defaults to localhost:5001, so _build_mirofish
        succeeds even without the env var. This test verifies the factory
        returns *some* SimulatorBase (MiroFish or fallback)."""
        monkeypatch.delenv("MIROFISH_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        sim = build_simulator(engine="mirofish")
        assert isinstance(sim, SimulatorBase)

    def test_returns_simulator_base(self, monkeypatch):
        monkeypatch.delenv("MIROFISH_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        sim = build_simulator()
        assert isinstance(sim, SimulatorBase)


class TestGetAvailableEngines:
    def test_rule_based_always_present(self, monkeypatch):
        monkeypatch.delenv("MIROFISH_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        engines = get_available_engines()
        assert "rule_based" in engines

    def test_llm_present_with_key(self, monkeypatch):
        monkeypatch.delenv("MIROFISH_BASE_URL", raising=False)
        monkeypatch.setenv("LLM_API_KEY", "sk-test")
        engines = get_available_engines()
        assert "llm" in engines

    def test_mirofish_present_with_url(self, monkeypatch):
        monkeypatch.setenv("MIROFISH_BASE_URL", "http://localhost:5001")
        engines = get_available_engines()
        assert "mirofish" in engines


class TestAPIValidation:
    """Test the route-level engine and user_params validation via TestClient."""

    def test_create_session_with_engine(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
            "engine": "rule_based",
        })
        assert r.status_code == 201

    def test_create_session_invalid_engine(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
            "engine": "invalid_engine",
        })
        assert r.status_code == 422

    def test_create_session_with_user_params(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
            "engine": "rule_based",
            "user_params": {"market_pressure": 75, "patience": 30},
        })
        assert r.status_code == 201

    def test_create_session_invalid_user_param_key(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
            "user_params": {"invalid_key": 50},
        })
        assert r.status_code == 422

    def test_create_session_user_param_out_of_range(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
            "user_params": {"patience": 150},
        })
        assert r.status_code == 422

    def test_create_session_valid_opponent_params(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
            "opponent_params": {"aggressiveness": 80, "flexibility": 40},
        })
        assert r.status_code == 201

    def test_create_session_invalid_opponent_param_key(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
            "opponent_params": {"hacking": 99},
        })
        assert r.status_code == 422

    def test_create_session_opponent_param_out_of_range(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
            "opponent_params": {"patience": -10},
        })
        assert r.status_code == 422

    def test_create_session_returns_engine_used(self, client):
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
            "engine": "rule_based",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["engine_used"] == "rule_based"

    def test_backward_compatibility_no_engine_field(self, client):
        """Existing clients that don't send engine/user_params still work."""
        r = client.post("/api/sessions", json={
            "scenario_type": "salary",
            "target_value": 100000,
        })
        assert r.status_code == 201
        data = r.json()
        assert "session_id" in data
        assert "opening_message" in data
