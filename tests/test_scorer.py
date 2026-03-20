"""Tests for the 6-dimension scoring system."""

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
from dealsim_mvp.core.scorer import (
    DimensionScore,
    Scorecard,
    generate_scorecard,
)


def _make_persona(**overrides) -> NegotiationPersona:
    defaults = dict(
        name="Test",
        role="Recruiter",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=85_000,
        reservation_price=115_000,
        opening_offer=80_000,
        patience=0.7,
        transparency=0.5,
        emotional_reactivity=0.3,
    )
    defaults.update(overrides)
    return NegotiationPersona(**defaults)


def _make_state(
    persona=None,
    user_opening_anchor=None,
    opponent_opening_anchor=None,
    user_last_offer=None,
    user_question_count=0,
    user_batna_signals=0,
    user_information_shares=0,
    user_concession_count=0,
    user_total_concession=0.0,
    opponent_total_concession=0.0,
    turn_count=5,
    resolved=False,
    agreed_value=None,
    transcript=None,
) -> NegotiationState:
    if persona is None:
        persona = _make_persona()
    state = NegotiationState(persona=persona)
    state.user_opening_anchor = user_opening_anchor
    state.opponent_opening_anchor = opponent_opening_anchor or persona.opening_offer
    state.user_last_offer = user_last_offer
    state.user_question_count = user_question_count
    state.user_batna_signals = user_batna_signals
    state.user_information_shares = user_information_shares
    state.user_concession_count = user_concession_count
    state.user_total_concession = user_total_concession
    state.opponent_total_concession = opponent_total_concession
    state.turn_count = turn_count
    state.resolved = resolved
    state.agreed_value = agreed_value
    state.transcript = transcript or []
    return state


# ---------------------------------------------------------------------------
# Opening Strategy
# ---------------------------------------------------------------------------

class TestOpeningStrategy:
    """High anchor relative to opponent opening => high Opening Strategy score."""

    def test_high_anchor_scores_high(self):
        state = _make_state(user_opening_anchor=100_000)
        # 100K vs 80K opening = 25% above => should score ~95
        sc = generate_scorecard(state, "test")
        opening = next(d for d in sc.dimensions if d.name == "Opening Strategy")
        assert opening.score >= 78

    def test_no_anchor_scores_low(self):
        state = _make_state(user_opening_anchor=None)
        sc = generate_scorecard(state, "test")
        opening = next(d for d in sc.dimensions if d.name == "Opening Strategy")
        assert opening.score <= 30

    def test_anchor_at_opponent_level_scores_low(self):
        state = _make_state(user_opening_anchor=80_000)
        sc = generate_scorecard(state, "test")
        opening = next(d for d in sc.dimensions if d.name == "Opening Strategy")
        assert opening.score <= 55


# ---------------------------------------------------------------------------
# Information Gathering
# ---------------------------------------------------------------------------

class TestInformationGathering:
    """Asking questions should increase Information Gathering score."""

    def test_many_questions_scores_high(self):
        state = _make_state(user_question_count=3, turn_count=5)
        sc = generate_scorecard(state, "test")
        info = next(d for d in sc.dimensions if d.name == "Information Gathering")
        assert info.score >= 70

    def test_no_questions_scores_low(self):
        state = _make_state(user_question_count=0, turn_count=5)
        sc = generate_scorecard(state, "test")
        info = next(d for d in sc.dimensions if d.name == "Information Gathering")
        assert info.score <= 20

    def test_some_questions_moderate_score(self):
        state = _make_state(user_question_count=1, turn_count=5)
        sc = generate_scorecard(state, "test")
        info = next(d for d in sc.dimensions if d.name == "Information Gathering")
        assert 15 < info.score < 90


# ---------------------------------------------------------------------------
# BATNA Usage
# ---------------------------------------------------------------------------

class TestBATNAUsage:
    """Mentioning alternatives should increase BATNA Usage score."""

    def test_one_batna_signal_scores_high(self):
        state = _make_state(user_batna_signals=1)
        sc = generate_scorecard(state, "test")
        batna = next(d for d in sc.dimensions if d.name == "BATNA Usage")
        assert batna.score >= 70

    def test_no_batna_scores_low(self):
        state = _make_state(user_batna_signals=0)
        sc = generate_scorecard(state, "test")
        batna = next(d for d in sc.dimensions if d.name == "BATNA Usage")
        assert batna.score <= 30

    def test_many_batna_signals_less_effective(self):
        state = _make_state(user_batna_signals=3)
        sc = generate_scorecard(state, "test")
        batna = next(d for d in sc.dimensions if d.name == "BATNA Usage")
        # Multiple BATNA signals score 65 (less than one at 80)
        assert batna.score < 80


# ---------------------------------------------------------------------------
# Concession Pattern
# ---------------------------------------------------------------------------

class TestConcessionPattern:
    """Rapid/large concessions should decrease score."""

    def test_no_concessions_with_deal_near_reservation_scores_high(self):
        """Deal without conceding that lands near reservation => high score."""
        state = _make_state(
            user_opening_anchor=112_000,
            user_concession_count=0,
            resolved=True,
            agreed_value=112_000,   # near reservation of 115K
        )
        sc = generate_scorecard(state, "test")
        conc = next(d for d in sc.dimensions if d.name == "Concession Pattern")
        assert conc.score >= 90

    def test_no_concessions_accept_first_offer_scores_low(self):
        """SCORE-01: accepting first offer without negotiating => low score."""
        state = _make_state(
            user_opening_anchor=None,
            user_concession_count=0,
            resolved=True,
            agreed_value=80_000,   # opponent's opening = 80K, reservation = 115K
        )
        sc = generate_scorecard(state, "test")
        conc = next(d for d in sc.dimensions if d.name == "Concession Pattern")
        assert conc.score <= 40

    def test_large_concessions_score_low(self):
        state = _make_state(
            user_opening_anchor=130_000,
            user_concession_count=3,
            user_total_concession=30_000,  # ~23% of anchor per step
        )
        sc = generate_scorecard(state, "test")
        conc = next(d for d in sc.dimensions if d.name == "Concession Pattern")
        assert conc.score < 50

    def test_small_concessions_score_high(self):
        state = _make_state(
            user_opening_anchor=130_000,
            user_concession_count=3,
            user_total_concession=6_000,  # ~1.5% per step
        )
        sc = generate_scorecard(state, "test")
        conc = next(d for d in sc.dimensions if d.name == "Concession Pattern")
        assert conc.score >= 70


# ---------------------------------------------------------------------------
# Scores in valid range
# ---------------------------------------------------------------------------

class TestScoreRange:
    """All dimension scores and overall must be 0-100."""

    def test_all_dimensions_in_range(self):
        state = _make_state(
            user_opening_anchor=120_000,
            user_question_count=2,
            user_batna_signals=1,
            user_concession_count=2,
            user_total_concession=10_000,
            turn_count=5,
        )
        sc = generate_scorecard(state, "test")
        for d in sc.dimensions:
            assert 0 <= d.score <= 100, f"{d.name} score {d.score} out of range"

    def test_overall_in_range(self):
        state = _make_state(
            user_opening_anchor=120_000,
            user_question_count=2,
            turn_count=5,
        )
        sc = generate_scorecard(state, "test")
        assert 0 <= sc.overall <= 100

    def test_extreme_low_state(self):
        """No anchors, no questions, no BATNA — all scores should still be valid."""
        state = _make_state()
        sc = generate_scorecard(state, "test")
        for d in sc.dimensions:
            assert 0 <= d.score <= 100

    def test_extreme_high_state(self):
        """Best possible performance signals."""
        # Build transcript with user turns containing package terms
        user_turns = [
            Turn(1, TurnSpeaker.USER, "I want $130,000 with equity and bonus and remote",
                 MoveType.ANCHOR, 130_000),
            Turn(3, TurnSpeaker.USER, "I have another offer", MoveType.BATNA_SIGNAL, None),
            Turn(5, TurnSpeaker.USER, "What about the budget?", MoveType.QUESTION, None),
        ]
        state = _make_state(
            user_opening_anchor=130_000,
            user_last_offer=128_000,
            user_question_count=3,
            user_batna_signals=1,
            user_information_shares=2,
            user_concession_count=1,
            user_total_concession=2_000,
            opponent_total_concession=5_000,
            turn_count=5,
            resolved=True,
            agreed_value=128_000,
            transcript=user_turns,
        )
        sc = generate_scorecard(state, "test")
        for d in sc.dimensions:
            assert 0 <= d.score <= 100
        assert sc.overall >= 50  # Should be decent overall


# ---------------------------------------------------------------------------
# Coaching tips
# ---------------------------------------------------------------------------

class TestCoachingTips:
    """Tips should be generated for low-scoring dimensions."""

    def test_tips_for_no_questions(self):
        state = _make_state(user_question_count=0, turn_count=5)
        sc = generate_scorecard(state, "test")
        info = next(d for d in sc.dimensions if d.name == "Information Gathering")
        assert len(info.tips) > 0

    def test_tips_for_no_batna(self):
        state = _make_state(user_batna_signals=0)
        sc = generate_scorecard(state, "test")
        batna = next(d for d in sc.dimensions if d.name == "BATNA Usage")
        assert len(batna.tips) > 0

    def test_no_tips_for_high_scores(self):
        state = _make_state(
            user_opening_anchor=130_000,
            user_question_count=5,
            turn_count=5,
        )
        sc = generate_scorecard(state, "test")
        info = next(d for d in sc.dimensions if d.name == "Information Gathering")
        # High question ratio => score >= 90 => no tips
        assert len(info.tips) == 0

    def test_top_tips_limited_to_three(self):
        state = _make_state()  # bare state => many low scores
        sc = generate_scorecard(state, "test")
        assert len(sc.top_tips) <= 3


# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------

class TestOutcome:
    def test_deal_reached(self):
        state = _make_state(resolved=True, agreed_value=100_000, turn_count=5)
        sc = generate_scorecard(state, "test")
        assert sc.outcome == "deal_reached"

    def test_no_deal(self):
        state = _make_state(resolved=False, turn_count=5)
        sc = generate_scorecard(state, "test")
        assert sc.outcome == "no_deal"

    def test_incomplete(self):
        state = _make_state(resolved=False, turn_count=1)
        sc = generate_scorecard(state, "test")
        assert sc.outcome == "incomplete"


# ---------------------------------------------------------------------------
# Scorecard structure
# ---------------------------------------------------------------------------

class TestScorecardStructure:
    def test_has_six_dimensions(self):
        state = _make_state()
        sc = generate_scorecard(state, "test-id")
        assert len(sc.dimensions) == 6

    def test_dimension_names(self):
        state = _make_state()
        sc = generate_scorecard(state, "test-id")
        names = {d.name for d in sc.dimensions}
        expected = {
            "Opening Strategy", "Information Gathering", "Concession Pattern",
            "BATNA Usage", "Emotional Control", "Value Creation",
        }
        assert names == expected

    def test_weights_sum_to_one(self):
        state = _make_state()
        sc = generate_scorecard(state, "test-id")
        total_weight = sum(d.weight for d in sc.dimensions)
        assert total_weight == pytest.approx(1.0)

    def test_session_id_propagated(self):
        state = _make_state()
        sc = generate_scorecard(state, "my-session-123")
        assert sc.session_id == "my-session-123"

    def test_persona_name_propagated(self):
        persona = _make_persona(name="Custom Name")
        state = _make_state(persona=persona)
        sc = generate_scorecard(state, "test")
        assert sc.persona_name == "Custom Name"
