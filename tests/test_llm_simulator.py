"""Tests for LLMSimulator — all LLM calls are mocked."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dealsim_mvp.core.llm_client import LLMClient, LLMConfig
from dealsim_mvp.core.llm_simulator import LLMSimulator
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

def _make_client(response_text: str = "I can offer $90,000.") -> LLMClient:
    """Return an LLMClient whose chat_completion always returns response_text."""
    cfg = LLMConfig(api_key="test", base_url="https://api.test.com/v1", model="m")
    client = LLMClient(cfg)
    client.chat_completion = AsyncMock(return_value=response_text)
    return client


def _make_simulator(response_text: str = "I can offer $90,000.") -> LLMSimulator:
    return LLMSimulator(client=_make_client(response_text))


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
    def test_implements_simulator_base(self, salary_persona):
        sim = _make_simulator()
        assert isinstance(sim, SimulatorBase)

    def test_initialize_state_returns_negotiation_state(self, salary_persona):
        sim = _make_simulator()
        state = sim.initialize_state(salary_persona)
        assert isinstance(state, NegotiationState)
        assert state.persona is salary_persona

    def test_initialize_state_is_clean(self, salary_persona):
        sim = _make_simulator()
        state = sim.initialize_state(salary_persona)
        assert state.turn_count == 0
        assert state.transcript == []
        assert not state.resolved


# ---------------------------------------------------------------------------
# opening_statement
# ---------------------------------------------------------------------------

class TestOpeningStatement:
    def test_returns_opponent_turn(self, salary_persona):
        sim = _make_simulator("Welcome! We're starting at $80,000.")
        state = sim.initialize_state(salary_persona)
        turn = sim.opening_statement(state)
        assert turn.speaker == TurnSpeaker.OPPONENT
        assert turn.turn_number == 0

    def test_appends_to_transcript(self, salary_persona):
        sim = _make_simulator("Starting offer is $80,000.")
        state = sim.initialize_state(salary_persona)
        sim.opening_statement(state)
        assert len(state.transcript) == 1
        assert state.transcript[0].speaker == TurnSpeaker.OPPONENT

    def test_sets_opponent_last_offer(self, salary_persona):
        sim = _make_simulator("We're offering $80,000 to start.")
        state = sim.initialize_state(salary_persona)
        sim.opening_statement(state)
        assert state.opponent_last_offer == 80_000

    def test_sets_opponent_opening_anchor(self, salary_persona):
        sim = _make_simulator("Our initial offer is $80,000.")
        state = sim.initialize_state(salary_persona)
        sim.opening_statement(state)
        assert state.opponent_opening_anchor == 80_000

    def test_move_type_is_anchor(self, salary_persona):
        sim = _make_simulator("Let's start at $80,000.")
        state = sim.initialize_state(salary_persona)
        turn = sim.opening_statement(state)
        assert turn.move_type == MoveType.ANCHOR

    def test_falls_back_on_llm_error(self, salary_persona):
        client = _make_client()
        client.chat_completion = AsyncMock(side_effect=Exception("timeout"))
        sim = LLMSimulator(client=client)
        state = sim.initialize_state(salary_persona)
        # Should not raise — falls back to rule-based
        turn = sim.opening_statement(state)
        assert turn.speaker == TurnSpeaker.OPPONENT
        assert state.opponent_last_offer is not None


# ---------------------------------------------------------------------------
# generate_response — general contract
# ---------------------------------------------------------------------------

class TestGenerateResponse:
    def test_returns_opponent_turn(self, salary_persona):
        sim = _make_simulator("I can offer $85,000.")
        state = _state_with_opening(salary_persona)
        turn = sim.generate_response(state, "I was thinking $100,000.")
        assert turn.speaker == TurnSpeaker.OPPONENT

    def test_appends_both_turns_to_transcript(self, salary_persona):
        sim = _make_simulator("How about $88,000?")
        state = _state_with_opening(salary_persona)
        before = len(state.transcript)
        sim.generate_response(state, "I want $100,000.")
        # user turn + opponent turn
        assert len(state.transcript) == before + 2

    def test_user_turn_appended_first(self, salary_persona):
        sim = _make_simulator("Okay, $87,000.")
        state = _state_with_opening(salary_persona)
        sim.generate_response(state, "Can you do $98,000?")
        # Second-to-last is user, last is opponent
        assert state.transcript[-2].speaker == TurnSpeaker.USER
        assert state.transcript[-1].speaker == TurnSpeaker.OPPONENT

    def test_increments_turn_count(self, salary_persona):
        sim = _make_simulator("Let me think... $87,500.")
        state = _state_with_opening(salary_persona)
        assert state.turn_count == 0
        sim.generate_response(state, "I'd like $100,000.")
        assert state.turn_count == 1

    def test_llm_text_is_in_returned_turn(self, salary_persona):
        response = "That works for me at $90,000."
        sim = _make_simulator(response)
        state = _state_with_opening(salary_persona)
        turn = sim.generate_response(state, "How about $90,000?")
        assert turn.text == response


# ---------------------------------------------------------------------------
# generate_response — offer parsing
# ---------------------------------------------------------------------------

class TestOfferParsing:
    def test_parses_offer_from_llm_response(self, salary_persona):
        sim = _make_simulator("We can do $95,000 for this role.")
        state = _state_with_opening(salary_persona)
        turn = sim.generate_response(state, "I need $100,000.")
        assert turn.offer_amount == 95_000

    def test_updates_opponent_last_offer(self, salary_persona):
        sim = _make_simulator("Best I can do is $92,000.")
        state = _state_with_opening(salary_persona)
        sim.generate_response(state, "I want $100,000.")
        assert state.opponent_last_offer == 92_000

    def test_no_offer_when_llm_asks_question(self, salary_persona):
        sim = _make_simulator("What kind of benefits are you looking for?")
        state = _state_with_opening(salary_persona)
        turn = sim.generate_response(state, "Tell me more about the role.")
        assert turn.offer_amount is None


# ---------------------------------------------------------------------------
# generate_response — acceptance detection
# ---------------------------------------------------------------------------

class TestAcceptanceDetection:
    def test_deal_signal_marks_resolved(self, salary_persona):
        sim = _make_simulator("Deal — let's move forward.")
        state = _state_with_opening(salary_persona)
        state.user_last_offer = 95_000  # simulate prior offer
        sim.generate_response(state, "I'll accept $95,000.")
        assert state.resolved is True

    def test_agreed_signal_marks_resolved(self, salary_persona):
        sim = _make_simulator("Agreed, that works for us.")
        state = _state_with_opening(salary_persona)
        state.user_last_offer = 93_000
        sim.generate_response(state, "Sounds good, $93,000.")
        assert state.resolved is True

    def test_acceptance_move_type(self, salary_persona):
        sim = _make_simulator("You've got a deal at that price.")
        state = _state_with_opening(salary_persona)
        state.user_last_offer = 92_000
        turn = sim.generate_response(state, "I accept $92,000.")
        assert turn.move_type == MoveType.ACCEPTANCE

    def test_resolved_false_when_counter_offer(self, salary_persona):
        sim = _make_simulator("I can do $88,000 but no higher.")
        state = _state_with_opening(salary_persona)
        sim.generate_response(state, "I want $100,000.")
        assert state.resolved is False


# ---------------------------------------------------------------------------
# generate_response — concession tracking
# ---------------------------------------------------------------------------

class TestConcessionTracking:
    def test_concession_increments_count(self, salary_persona):
        # salary_persona: reservation > opening, so opponent moving UP = concession
        # First call sets opponent_last_offer = 85,000
        # Second call at 90,000 is a concession toward user
        client = _make_client()
        client.chat_completion = AsyncMock(side_effect=[
            "We can offer $85,000.",
            "Moving up to $90,000.",
        ])
        sim = LLMSimulator(client=client)
        state = _state_with_opening(salary_persona)

        sim.generate_response(state, "I need $100,000.")   # sets opponent_last=85k
        sim.generate_response(state, "Please, $100,000.")  # moves to 90k = concession

        assert state.opponent_concession_count >= 1

    def test_concession_updates_total(self, salary_persona):
        client = _make_client()
        client.chat_completion = AsyncMock(side_effect=[
            "Starting at $83,000.",
            "I'll go to $88,000.",
        ])
        sim = LLMSimulator(client=client)
        state = _state_with_opening(salary_persona)

        sim.generate_response(state, "I want $100,000.")
        sim.generate_response(state, "Still $100,000.")

        assert state.opponent_total_concession > 0

    def test_concession_from_field_set(self, salary_persona):
        client = _make_client()
        client.chat_completion = AsyncMock(side_effect=[
            "First offer: $82,000.",
            "I'll move to $87,000.",
        ])
        sim = LLMSimulator(client=client)
        state = _state_with_opening(salary_persona)

        sim.generate_response(state, "I want $100,000.")
        turn = sim.generate_response(state, "Still $100,000.")

        if turn.move_type == MoveType.CONCESSION:
            assert turn.concession_from == 82_000


# ---------------------------------------------------------------------------
# Fallback on LLM error
# ---------------------------------------------------------------------------

class TestFallback:
    def test_generate_falls_back_on_exception(self, salary_persona):
        client = _make_client()
        client.chat_completion = AsyncMock(side_effect=Exception("API down"))
        fallback = RuleBasedSimulator()
        sim = LLMSimulator(client=client, fallback=fallback)

        state = _state_with_opening(salary_persona)
        turn = sim.generate_response(state, "I want $100,000.")

        # Rule-based fallback should have produced a valid turn
        assert turn.speaker == TurnSpeaker.OPPONENT
        assert turn.text  # non-empty

    def test_opening_falls_back_on_exception(self, salary_persona):
        client = _make_client()
        client.chat_completion = AsyncMock(side_effect=ConnectionError("refused"))
        sim = LLMSimulator(client=client)

        state = sim.initialize_state(salary_persona)
        turn = sim.opening_statement(state)

        assert turn.speaker == TurnSpeaker.OPPONENT
        assert state.opponent_last_offer is not None

    def test_custom_fallback_is_used(self, salary_persona):
        """Verify the injected fallback (not a new instance) is called."""
        client = _make_client()
        client.chat_completion = AsyncMock(side_effect=Exception("fail"))

        fallback = RuleBasedSimulator()
        called = []
        original = fallback.generate_response

        def tracking_generate(state, user_text):
            called.append(user_text)
            return original(state, user_text)

        fallback.generate_response = tracking_generate
        sim = LLMSimulator(client=client, fallback=fallback)

        state = _state_with_opening(salary_persona)
        sim.generate_response(state, "test message")

        assert "test message" in called


# ---------------------------------------------------------------------------
# System prompt construction
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_includes_persona_system_prompt(self, salary_persona):
        salary_persona.system_prompt = "You are a test recruiter."
        sim = _make_simulator()
        prompt = sim._build_system_prompt(salary_persona)
        assert "You are a test recruiter." in prompt

    def test_includes_negotiation_instructions(self, salary_persona):
        sim = _make_simulator()
        prompt = sim._build_system_prompt(salary_persona)
        assert "Stay in character" in prompt
        assert "dollar" in prompt.lower() or "$" in prompt

    def test_fallback_prompt_when_no_system_prompt(self, salary_persona):
        salary_persona.system_prompt = ""
        sim = _make_simulator()
        prompt = sim._build_system_prompt(salary_persona)
        assert salary_persona.name in prompt
        assert salary_persona.role in prompt


# ---------------------------------------------------------------------------
# Message history construction
# ---------------------------------------------------------------------------

class TestMessageHistory:
    def test_excludes_opening_turn(self, salary_persona):
        """Turn 0 (opening) must not appear as a duplicate in history."""
        sim = _make_simulator()
        state = _state_with_opening(salary_persona)
        # Only the opening turn is in transcript
        messages = sim._build_message_history(state)
        assert messages == []

    def test_user_mapped_to_user_role(self, salary_persona):
        sim = _make_simulator("counter offer")
        state = _state_with_opening(salary_persona)
        sim.generate_response(state, "I want $100,000.")
        messages = sim._build_message_history(state)
        user_msgs = [m for m in messages if m["role"] == "user"]
        assert any("$100,000" in m["content"] or "100,000" in m["content"] or "100000" in m["content"] or "I want" in m["content"] for m in user_msgs)

    def test_opponent_mapped_to_assistant_role(self, salary_persona):
        response = "I can do $88,000."
        sim = _make_simulator(response)
        state = _state_with_opening(salary_persona)
        sim.generate_response(state, "I want $100,000.")
        messages = sim._build_message_history(state)
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert any(response in m["content"] for m in assistant_msgs)
