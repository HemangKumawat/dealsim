"""Tests for the rule-based negotiation engine."""

import pytest

from dealsim_mvp.core.persona import NegotiationStyle, PressureLevel
from dealsim_mvp.core.simulator import (
    MoveType,
    NegotiationState,
    RuleBasedSimulator,
    Turn,
    TurnSpeaker,
    _extract_offer,
    _classify_user_move,
)


# ---------------------------------------------------------------------------
# Offer extraction
# ---------------------------------------------------------------------------

class TestExtractOffer:
    """_extract_offer should parse monetary values from various formats."""

    @pytest.mark.parametrize("text, expected", [
        ("I'd like $120,000", 120_000),
        ("How about $120K", 120_000),
        ("120k works for me", 120_000),
        ("I'm thinking 120000", 120_000),
        ("$120,000 is fair", 120_000),
        ("$120,000.00", 120_000),
        ("Let's say 85k", 85_000),
        ("$75", 75),
        ("$75.50 per hour", 75.50),
    ])
    def test_various_formats(self, text, expected):
        result = _extract_offer(text)
        assert result == pytest.approx(expected)

    def test_no_number_returns_none(self):
        assert _extract_offer("I'd like to discuss the role") is None

    def test_empty_string_returns_none(self):
        assert _extract_offer("") is None

    def test_multiple_numbers_returns_largest(self):
        result = _extract_offer("The range is $80,000 to $120,000")
        assert result == pytest.approx(120_000)

    def test_k_suffix_case_insensitive(self):
        assert _extract_offer("150K") == pytest.approx(150_000)
        assert _extract_offer("150k") == pytest.approx(150_000)


# ---------------------------------------------------------------------------
# Move classification
# ---------------------------------------------------------------------------

class TestClassifyUserMove:
    """_classify_user_move should identify move types from message content."""

    @pytest.fixture
    def fresh_state(self, salary_persona, simulator):
        state = simulator.initialize_state(salary_persona)
        simulator.opening_statement(state)
        return state

    def test_acceptance_signals(self, fresh_state):
        for phrase in ["That sounds good", "Deal!", "I'll accept that", "Works for me"]:
            move, _ = _classify_user_move(phrase, fresh_state)
            assert move == MoveType.ACCEPTANCE, f"Failed on: {phrase}"

    def test_batna_signals(self, fresh_state):
        for phrase in [
            "I have another offer on the table",
            "I could walk away",
            "I have a competing offer at 130K",
        ]:
            move, _ = _classify_user_move(phrase, fresh_state)
            assert move == MoveType.BATNA_SIGNAL, f"Failed on: {phrase}"

    def test_question_signals(self, fresh_state):
        move, _ = _classify_user_move("What's your budget range?", fresh_state)
        assert move == MoveType.QUESTION

    def test_question_with_offer_is_counter(self, fresh_state):
        move, offer = _classify_user_move("Would $120,000 work?", fresh_state)
        assert move == MoveType.COUNTER_OFFER
        assert offer == pytest.approx(120_000)

    def test_first_offer_is_anchor(self, fresh_state):
        move, offer = _classify_user_move("I'm looking for $130,000", fresh_state)
        assert move == MoveType.ANCHOR
        assert offer == pytest.approx(130_000)

    def test_subsequent_lower_offer_is_concession(self, fresh_state):
        fresh_state.user_last_offer = 130_000
        fresh_state.user_opening_anchor = 130_000
        move, offer = _classify_user_move("I can come down to $120,000", fresh_state)
        assert move == MoveType.CONCESSION
        assert offer == pytest.approx(120_000)

    def test_information_share(self, fresh_state):
        # Note: avoid words containing question substrings (e.g. "shows" contains "how")
        # and avoid numbers (which get extracted as offers and trigger ANCHOR)
        move, _ = _classify_user_move(
            "Because I've been in this field a long time, I bring significant value", fresh_state
        )
        assert move == MoveType.INFORMATION_SHARE

    def test_unknown_for_generic_message(self, fresh_state):
        move, _ = _classify_user_move("Let me think about it", fresh_state)
        assert move == MoveType.UNKNOWN


# ---------------------------------------------------------------------------
# Opponent response generation
# ---------------------------------------------------------------------------

class TestOpponentResponse:
    """RuleBasedSimulator.generate_response should produce valid turns."""

    def test_returns_turn_object(self, negotiation_state, simulator):
        turn = simulator.generate_response(negotiation_state, "I want $120,000")
        assert isinstance(turn, Turn)
        assert turn.speaker == TurnSpeaker.OPPONENT

    def test_response_has_text(self, negotiation_state, simulator):
        turn = simulator.generate_response(negotiation_state, "I want $120,000")
        assert isinstance(turn.text, str) and len(turn.text) > 0

    def test_turn_number_increments(self, negotiation_state, simulator):
        t1 = simulator.generate_response(negotiation_state, "I want $120K")
        t2 = simulator.generate_response(negotiation_state, "How about $115K")
        assert t2.turn_number > t1.turn_number


class TestDealAcceptance:
    """Opponent should accept when user offer is within reservation price."""

    def test_accepts_offer_within_reservation(self, salary_persona, simulator):
        """salary_persona: reservation=115K, opening=80K. User offers 110K (below 115K)."""
        state = simulator.initialize_state(salary_persona)
        simulator.opening_statement(state)
        turn = simulator.generate_response(state, "I'll take $110,000")
        assert state.resolved is True
        assert state.agreed_value == pytest.approx(110_000)
        assert turn.move_type == MoveType.ACCEPTANCE

    def test_rejects_offer_above_reservation(self, salary_persona, simulator):
        """User offers 130K -- above reservation of 115K, should NOT accept."""
        state = simulator.initialize_state(salary_persona)
        simulator.opening_statement(state)
        turn = simulator.generate_response(state, "I need $130,000")
        assert state.resolved is False

    def test_explicit_acceptance_resolves(self, salary_persona, simulator):
        state = simulator.initialize_state(salary_persona)
        simulator.opening_statement(state)
        turn = simulator.generate_response(state, "That sounds good, deal!")
        assert state.resolved is True


class TestOpponentConcessionByStyle:
    """Different styles should produce different concession magnitudes."""

    def test_competitive_concedes_less_than_collaborative(
        self, competitive_persona, salary_persona, simulator
    ):
        state_comp = simulator.initialize_state(competitive_persona)
        simulator.opening_statement(state_comp)
        t_comp = simulator.generate_response(state_comp, "I want $120,000")

        state_collab = simulator.initialize_state(salary_persona)
        simulator.opening_statement(state_collab)
        t_collab = simulator.generate_response(state_collab, "I want $120,000")

        if t_comp.offer_amount is not None and t_collab.offer_amount is not None:
            comp_move = abs(t_comp.offer_amount - competitive_persona.opening_offer)
            collab_move = abs(t_collab.offer_amount - salary_persona.opening_offer)
            assert comp_move <= collab_move

    def test_accommodating_concedes_most(
        self, accommodating_persona, competitive_persona, simulator
    ):
        state_acc = simulator.initialize_state(accommodating_persona)
        simulator.opening_statement(state_acc)
        t_acc = simulator.generate_response(state_acc, "I want $120,000")

        state_comp = simulator.initialize_state(competitive_persona)
        simulator.opening_statement(state_comp)
        t_comp = simulator.generate_response(state_comp, "I want $120,000")

        if t_acc.offer_amount is not None and t_comp.offer_amount is not None:
            acc_move = abs(t_acc.offer_amount - accommodating_persona.opening_offer)
            comp_move = abs(t_comp.offer_amount - competitive_persona.opening_offer)
            assert acc_move >= comp_move


class TestEdgeCases:
    """Edge cases: empty, long, no-number, multi-number messages."""

    def test_empty_message(self, negotiation_state, simulator):
        turn = simulator.generate_response(negotiation_state, "")
        assert isinstance(turn, Turn)
        assert turn.speaker == TurnSpeaker.OPPONENT

    def test_very_long_message(self, negotiation_state, simulator):
        long_msg = "I think " * 500 + "we should settle at $110,000."
        turn = simulator.generate_response(negotiation_state, long_msg)
        assert isinstance(turn, Turn)

    def test_no_numbers_message(self, negotiation_state, simulator):
        turn = simulator.generate_response(
            negotiation_state, "Tell me more about the role and team culture"
        )
        assert isinstance(turn, Turn)
        user_turn = negotiation_state.transcript[-2]
        assert user_turn.move_type == MoveType.QUESTION

    def test_multiple_numbers(self, negotiation_state, simulator):
        turn = simulator.generate_response(
            negotiation_state, "The range is between $100,000 and $130,000"
        )
        user_turn = negotiation_state.transcript[-2]
        assert user_turn.offer_amount == pytest.approx(130_000)


class TestOpeningStatement:
    """opening_statement should set state and return an anchor turn."""

    def test_returns_anchor_turn(self, salary_persona, simulator):
        state = simulator.initialize_state(salary_persona)
        turn = simulator.opening_statement(state)
        assert turn.move_type == MoveType.ANCHOR
        assert turn.speaker == TurnSpeaker.OPPONENT
        assert turn.offer_amount == pytest.approx(salary_persona.opening_offer)

    def test_sets_opponent_opening_anchor(self, salary_persona, simulator):
        state = simulator.initialize_state(salary_persona)
        simulator.opening_statement(state)
        assert state.opponent_opening_anchor == salary_persona.opening_offer
        assert state.opponent_last_offer == salary_persona.opening_offer

    def test_appends_to_transcript(self, salary_persona, simulator):
        state = simulator.initialize_state(salary_persona)
        simulator.opening_statement(state)
        assert len(state.transcript) == 1
        assert state.transcript[0].speaker == TurnSpeaker.OPPONENT
