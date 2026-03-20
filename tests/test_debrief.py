"""Tests for debrief generation (core and API layers)."""

import pytest

from dealsim_mvp.core.persona import (
    NegotiationPersona,
    NegotiationStyle,
    PressureLevel,
)
from dealsim_mvp.core.simulator import (
    MoveType,
    NegotiationState,
    RuleBasedSimulator,
    Turn,
    TurnSpeaker,
)
from dealsim_mvp.core.debrief import (
    DebriefResult,
    HiddenStateSnapshot,
    MoveAnalysis,
    generate_debrief,
)
from dealsim_mvp.api.debrief import (
    DebriefReport,
    generate_debrief as api_generate_debrief,
    generate_playbook as api_generate_playbook,
    Playbook,
)


def _persona(**overrides) -> NegotiationPersona:
    defaults = dict(
        name="Test Recruiter",
        role="HR Director",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=85_000,
        reservation_price=115_000,
        opening_offer=80_000,
        patience=0.7,
        transparency=0.5,
        emotional_reactivity=0.3,
        hidden_constraints=["Budget ceiling is 120K"],
    )
    defaults.update(overrides)
    return NegotiationPersona(**defaults)


def _state_with_transcript(persona=None, resolved=False, agreed_value=None, turns=None):
    """Build a NegotiationState with a pre-set transcript."""
    p = persona or _persona()
    state = NegotiationState(persona=p)
    state.opponent_opening_anchor = p.opening_offer
    state.opponent_last_offer = p.opening_offer
    state.resolved = resolved
    state.agreed_value = agreed_value
    if turns is not None:
        state.transcript = turns
        # Derive some state fields from transcript
        for t in turns:
            if t.speaker == TurnSpeaker.USER and t.offer_amount is not None:
                if state.user_opening_anchor is None:
                    state.user_opening_anchor = t.offer_amount
                state.user_last_offer = t.offer_amount
            if t.speaker == TurnSpeaker.USER and t.move_type == MoveType.QUESTION:
                state.user_question_count += 1
            if t.speaker == TurnSpeaker.USER and t.move_type == MoveType.BATNA_SIGNAL:
                state.user_batna_signals += 1
    return state


# ---------------------------------------------------------------------------
# Core debrief: generate_debrief
# ---------------------------------------------------------------------------

class TestGenerateDebrief:
    """generate_debrief should produce a complete DebriefResult."""

    def test_returns_debrief_result(self):
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "We can offer $80,000.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "I'd like $130,000.", MoveType.ANCHOR, 130_000),
            Turn(3, TurnSpeaker.OPPONENT, "How about $90,000?", MoveType.CONCESSION, 90_000),
        ]
        state = _state_with_transcript(turns=turns)
        result = generate_debrief(state)
        assert isinstance(result, DebriefResult)

    def test_deal_reached_money_left(self):
        """When a deal is reached below reservation, money_left_on_table > 0."""
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "We offer $80,000.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "How about $100,000?", MoveType.ANCHOR, 100_000),
            Turn(3, TurnSpeaker.OPPONENT, "Deal!", MoveType.ACCEPTANCE, 100_000),
        ]
        state = _state_with_transcript(resolved=True, agreed_value=100_000, turns=turns)
        result = generate_debrief(state)
        # Reservation is 115K, deal at 100K => 15K left
        assert result.money_left_on_table == 15_000.0
        assert result.deal_reached is True
        assert result.agreed_value == 100_000

    def test_no_deal_money_left(self):
        """When no deal, money_left_on_table = distance from user's last offer to reservation."""
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "We offer $80,000.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "I need $200,000.", MoveType.ANCHOR, 200_000),
        ]
        state = _state_with_transcript(resolved=False, turns=turns)
        result = generate_debrief(state)
        # DEBRIEF-01: No deal, user's last offer=$200K, reservation=$115K
        # => money_left = |115K - 200K| = 85K (how far from a deal the user was)
        assert result.money_left_on_table == 85_000.0
        assert result.deal_reached is False

    def test_no_deal_no_user_offer_money_left(self):
        """When no deal and user never offered, money_left_on_table = full range."""
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "We offer $80,000.", MoveType.ANCHOR, 80_000),
        ]
        state = _state_with_transcript(resolved=False, turns=turns)
        result = generate_debrief(state)
        # No user offer => falls back to |reservation - opening| = |115K - 80K| = 35K
        assert result.money_left_on_table == 35_000.0

    def test_optimal_outcome_equals_reservation(self):
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Opening.", MoveType.ANCHOR, 80_000),
        ]
        state = _state_with_transcript(turns=turns)
        result = generate_debrief(state)
        assert result.optimal_outcome == 115_000.0

    def test_move_analysis_populated(self):
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer $80K.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "Counter at $120K.", MoveType.ANCHOR, 120_000),
        ]
        state = _state_with_transcript(turns=turns)
        result = generate_debrief(state)
        assert len(result.move_analysis) >= 2

    def test_hidden_state_timeline_populated(self):
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "Counter.", MoveType.ANCHOR, 120_000),
        ]
        state = _state_with_transcript(turns=turns)
        result = generate_debrief(state)
        assert len(result.hidden_state_timeline) >= 1

    def test_undiscovered_constraints_when_no_questions(self):
        """If user never asks about hidden constraints, they appear in undiscovered."""
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "I want $120K.", MoveType.ANCHOR, 120_000),
        ]
        persona = _persona(hidden_constraints=["Board approval required for above 110K"])
        state = _state_with_transcript(persona=persona, turns=turns)
        result = generate_debrief(state)
        assert len(result.undiscovered_constraints) > 0

    def test_empty_transcript(self):
        """Debrief with empty transcript should not crash."""
        state = _state_with_transcript(turns=[])
        result = generate_debrief(state)
        assert isinstance(result, DebriefResult)
        assert result.closest_to_deal == 0

    def test_reservation_price_revealed(self):
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
        ]
        state = _state_with_transcript(turns=turns)
        result = generate_debrief(state)
        assert result.reservation_price == 115_000


# ---------------------------------------------------------------------------
# API debrief: generate_debrief (wrapper) and generate_playbook
# ---------------------------------------------------------------------------

class TestAPIDebriefGeneration:
    """API-level debrief generation via dealsim_mvp.api.debrief."""

    def test_returns_debrief_report(self):
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer $80K.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "$120K please.", MoveType.ANCHOR, 120_000),
        ]
        state = _state_with_transcript(turns=turns)
        report = api_generate_debrief(state, "test-session")
        assert isinstance(report, DebriefReport)
        assert report.session_id == "test-session"
        assert report.opponent_reservation == 115_000

    def test_outcome_grade_with_no_deal(self):
        state = _state_with_transcript(turns=[])
        report = api_generate_debrief(state, "s1")
        assert report.outcome_grade == "incomplete"


class TestAPIPlaybookGeneration:
    """API-level playbook generation."""

    def test_returns_playbook(self):
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "$120K.", MoveType.ANCHOR, 120_000),
        ]
        state = _state_with_transcript(turns=turns)
        pb = api_generate_playbook(state, "sess-1", 72)
        assert isinstance(pb, Playbook)
        assert pb.session_id == "sess-1"
        assert pb.overall_score == 72

    def test_playbook_detects_weak_anchor(self):
        """If user never anchored, playbook should flag it."""
        state = _state_with_transcript(turns=[
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
        ])
        pb = api_generate_playbook(state, "s1", 30)
        assert any("anchor" in w.lower() for w in pb.weaknesses)

    def test_playbook_detects_no_questions(self):
        state = _state_with_transcript(turns=[
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "I want $130K.", MoveType.ANCHOR, 130_000),
        ])
        pb = api_generate_playbook(state, "s1", 40)
        assert any("question" in w.lower() for w in pb.weaknesses)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestDebriefEdgeCases:
    """Edge cases for debrief generation."""

    def test_single_user_acceptance_turn(self):
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "We offer $80K.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "Deal!", MoveType.ACCEPTANCE, 80_000),
        ]
        state = _state_with_transcript(resolved=True, agreed_value=80_000, turns=turns)
        result = generate_debrief(state)
        # All reservation - agreed left on table
        assert result.money_left_on_table == 35_000.0

    def test_all_opponent_turns(self):
        """Transcript with only opponent turns (no user messages)."""
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.OPPONENT, "Waiting.", MoveType.PRESSURE, None),
        ]
        state = _state_with_transcript(turns=turns)
        result = generate_debrief(state)
        assert isinstance(result, DebriefResult)

    def test_persona_with_no_hidden_constraints(self):
        persona = _persona(hidden_constraints=[])
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
        ]
        state = _state_with_transcript(persona=persona, turns=turns)
        result = generate_debrief(state)
        assert result.undiscovered_constraints == []
