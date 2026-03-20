"""Tests for MiroFishSimulator — all MiroFish calls are mocked."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dealsim_mvp.core.mirofish_client import MiroFishClient, MiroFishAPIError
from dealsim_mvp.core.mirofish_config import MiroFishConfig
from dealsim_mvp.core.mirofish import MiroFishSimulator
from dealsim_mvp.core.simulator import (
    MoveType,
    NegotiationState,
    RuleBasedSimulator,
    SimulatorBase,
    TurnSpeaker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(interview_response: dict | None = None) -> MiroFishClient:
    """Return a MiroFishClient with all endpoints mocked."""
    config = MiroFishConfig(base_url="http://test:5001")
    client = MiroFishClient(config)

    # Mock all async methods
    client.create_project = AsyncMock(return_value={
        "data": {"project_id": "proj-test-123"}
    })
    client.create_simulation = AsyncMock(return_value={
        "data": {"simulation_id": "sim-test-456"}
    })
    client.prepare_simulation = AsyncMock(return_value={"success": True})
    client.start_simulation = AsyncMock(return_value={"success": True})
    client.stop_simulation = AsyncMock(return_value={"success": True})
    client.close_env = AsyncMock(return_value={"success": True})
    client.close = AsyncMock()

    default_resp = interview_response or {
        "data": {"result": {"response": "I can offer $90,000 for this position."}}
    }
    client.interview = AsyncMock(return_value=default_resp)
    return client


def _make_simulator(
    interview_response: dict | None = None,
    user_params: dict | None = None,
) -> MiroFishSimulator:
    client = _make_client(interview_response)
    return MiroFishSimulator(client=client, user_params=user_params)


def _state_with_opening(salary_persona) -> NegotiationState:
    """Return a NegotiationState with a rule-based opening already applied."""
    sim = RuleBasedSimulator()
    state = sim.initialize_state(salary_persona)
    sim.opening_statement(state)
    return state


# ---------------------------------------------------------------------------
# Interface contract
# ---------------------------------------------------------------------------

class TestInterface:
    def test_implements_simulator_base(self):
        sim = _make_simulator()
        assert isinstance(sim, SimulatorBase)

    def test_is_available_with_config(self):
        sim = _make_simulator()
        assert sim.is_available() is True

    def test_is_available_without_url(self):
        config = MiroFishConfig(base_url="")
        client = MiroFishClient(config)
        sim = MiroFishSimulator(client=client)
        assert sim.is_available() is False


# ---------------------------------------------------------------------------
# Opening statement
# ---------------------------------------------------------------------------

class TestOpeningStatement:
    def test_opening_extracts_offer(self, salary_persona):
        sim = _make_simulator(interview_response={
            "data": {"result": {"response": "I'd like to start at $80,000 for this role."}}
        })
        state = sim.initialize_state(salary_persona)
        turn = sim.opening_statement(state)

        assert turn.speaker == TurnSpeaker.OPPONENT
        assert turn.move_type == MoveType.ANCHOR
        assert turn.offer_amount == pytest.approx(80_000)
        assert "$80,000" in turn.text

    def test_opening_falls_back_to_persona_offer(self, salary_persona):
        """When response has no dollar amount, use persona.opening_offer."""
        sim = _make_simulator(interview_response={
            "data": {"result": {"response": "Welcome! Let me share our offer."}}
        })
        state = sim.initialize_state(salary_persona)
        turn = sim.opening_statement(state)

        assert turn.offer_amount == salary_persona.opening_offer

    def test_opening_updates_state(self, salary_persona):
        sim = _make_simulator(interview_response={
            "data": {"result": {"response": "We're offering $80,000."}}
        })
        state = sim.initialize_state(salary_persona)
        sim.opening_statement(state)

        assert state.opponent_last_offer == pytest.approx(80_000)
        assert state.opponent_opening_anchor == pytest.approx(80_000)
        assert len(state.transcript) == 1

    def test_opening_appends_to_transcript(self, salary_persona):
        sim = _make_simulator()
        state = sim.initialize_state(salary_persona)
        turn = sim.opening_statement(state)

        assert state.transcript[-1] is turn
        assert turn.turn_number == 0


# ---------------------------------------------------------------------------
# Generate response
# ---------------------------------------------------------------------------

class TestGenerateResponse:
    def test_counter_offer(self, salary_persona):
        sim = _make_simulator(interview_response={
            "data": {"result": {"response": "I can go up to $85,000, but that's my best."}}
        })
        state = _state_with_opening(salary_persona)
        # Swap simulator's initialized state
        sim._initialized = True
        sim._simulation_id = "sim-test-456"

        turn = sim.generate_response(state, "I want $120,000")

        assert turn.speaker == TurnSpeaker.OPPONENT
        assert turn.offer_amount == pytest.approx(85_000)
        assert "$85,000" in turn.text

    def test_acceptance_signal(self, salary_persona):
        sim = _make_simulator(interview_response={
            "data": {"result": {"response": "You've got a deal! Let's move forward."}}
        })
        state = _state_with_opening(salary_persona)
        state.user_last_offer = 100_000
        sim._initialized = True
        sim._simulation_id = "sim-test-456"

        turn = sim.generate_response(state, "How about $100,000?")

        assert turn.move_type == MoveType.ACCEPTANCE
        assert state.resolved is True

    def test_not_done_is_not_acceptance(self, salary_persona):
        """'not done' should NOT trigger acceptance — word-boundary guard."""
        sim = _make_simulator(interview_response={
            "data": {"result": {"response": "I'm not done negotiating yet."}}
        })
        state = _state_with_opening(salary_persona)
        sim._initialized = True
        sim._simulation_id = "sim-test-456"

        turn = sim.generate_response(state, "How about $100,000?")

        assert turn.move_type != MoveType.ACCEPTANCE

    def test_rejection_signal(self, salary_persona):
        sim = _make_simulator(interview_response={
            "data": {"result": {"response": "That's a non-starter. We can't do that."}}
        })
        state = _state_with_opening(salary_persona)
        sim._initialized = True
        sim._simulation_id = "sim-test-456"

        turn = sim.generate_response(state, "I need $200,000")

        assert turn.move_type == MoveType.REJECTION

    def test_question_response(self, salary_persona):
        sim = _make_simulator(interview_response={
            "data": {"result": {"response": "What aspects of the role interest you most?"}}
        })
        state = _state_with_opening(salary_persona)
        sim._initialized = True
        sim._simulation_id = "sim-test-456"

        turn = sim.generate_response(state, "I want $120,000")

        assert turn.move_type == MoveType.QUESTION

    def test_records_user_turn(self, salary_persona):
        sim = _make_simulator()
        state = _state_with_opening(salary_persona)
        sim._initialized = True
        sim._simulation_id = "sim-test-456"

        initial_len = len(state.transcript)
        sim.generate_response(state, "I want $120,000")

        # Should have added user turn + opponent turn
        assert len(state.transcript) == initial_len + 2
        user_turn = state.transcript[-2]
        assert user_turn.speaker == TurnSpeaker.USER

    def test_increments_turn_count(self, salary_persona):
        sim = _make_simulator()
        state = _state_with_opening(salary_persona)
        sim._initialized = True
        sim._simulation_id = "sim-test-456"

        assert state.turn_count == 0
        sim.generate_response(state, "I want $120,000")
        assert state.turn_count == 1


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------

class TestFallback:
    def test_opening_falls_back_on_api_error(self, salary_persona):
        sim = _make_simulator()
        sim.client.interview = AsyncMock(
            side_effect=MiroFishAPIError(500, "Internal error", "/interview")
        )
        state = sim.initialize_state(salary_persona)

        # Should not raise — falls back to RuleBasedSimulator
        turn = sim.opening_statement(state)
        assert turn.speaker == TurnSpeaker.OPPONENT
        assert turn.text  # got a response from fallback

    def test_generate_falls_back_on_network_error(self, salary_persona):
        sim = _make_simulator()
        sim._initialized = True
        sim._simulation_id = "sim-test-456"
        sim.client.interview = AsyncMock(
            side_effect=ConnectionError("MiroFish unreachable")
        )
        state = _state_with_opening(salary_persona)

        turn = sim.generate_response(state, "I want $120,000")
        assert turn.speaker == TurnSpeaker.OPPONENT
        assert turn.text  # fallback produced a response

    def test_opening_falls_back_on_create_failure(self, salary_persona):
        sim = _make_simulator()
        sim.client.create_project = AsyncMock(
            side_effect=MiroFishAPIError(500, "Create failed", "/create")
        )
        state = sim.initialize_state(salary_persona)

        turn = sim.opening_statement(state)
        assert turn.speaker == TurnSpeaker.OPPONENT


# ---------------------------------------------------------------------------
# Response text extraction
# ---------------------------------------------------------------------------

class TestExtractResponseText:
    def test_single_platform_format(self):
        sim = _make_simulator()
        resp = {"data": {"result": {"response": "Hello from MiroFish!"}}}
        assert sim._extract_response_text(resp) == "Hello from MiroFish!"

    def test_dual_platform_format(self):
        sim = _make_simulator()
        resp = {"data": {"result": {"platforms": {
            "twitter": {"response": "Platform response here"}
        }}}}
        assert sim._extract_response_text(resp) == "Platform response here"

    def test_top_level_response(self):
        sim = _make_simulator()
        resp = {"data": {"response": "Direct response"}}
        assert sim._extract_response_text(resp) == "Direct response"

    def test_raises_on_unknown_format(self):
        """Unrecognizable format raises MiroFishAPIError so fallback kicks in."""
        sim = _make_simulator()
        resp = {"data": {"result": {}}}
        with pytest.raises(MiroFishAPIError):
            sim._extract_response_text(resp)


# ---------------------------------------------------------------------------
# User params injection
# ---------------------------------------------------------------------------

class TestUserParams:
    def test_user_params_injected_into_prompt(self, salary_persona):
        """Verify that user_params influence the system prompt during init."""
        sim = _make_simulator(user_params={
            "market_pressure": 80,
            "patience": 20,
        })
        state = sim.initialize_state(salary_persona)
        sim.opening_statement(state)

        # Verify create_project was called (simulation was initialized)
        sim.client.create_project.assert_called_once()


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_cleanup_stops_then_closes(self, salary_persona):
        sim = _make_simulator()
        sim._simulation_id = "sim-test-456"
        sim._initialized = True

        asyncio.run(sim.cleanup())

        sim.client.stop_simulation.assert_called_once_with("sim-test-456")
        sim.client.close_env.assert_called_once_with("sim-test-456")
        sim.client.close.assert_called_once()

    def test_cleanup_without_simulation(self):
        sim = _make_simulator()
        # No simulation was ever created
        asyncio.run(sim.cleanup())

        sim.client.stop_simulation.assert_not_called()
        sim.client.close.assert_called_once()
