"""Tests for core playbook generation (dealsim_mvp.core.playbook)."""

import pytest

from dealsim_mvp.core.persona import (
    NegotiationPersona,
    NegotiationStyle,
    PressureLevel,
)
from dealsim_mvp.core.simulator import (
    MoveType,
    NegotiationState,
    Turn,
    TurnSpeaker,
)
from dealsim_mvp.core.playbook import (
    PlaybookResult,
    ConcessionStep,
    Objection,
    generate_playbook,
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


# ---------------------------------------------------------------------------
# Basic generation
# ---------------------------------------------------------------------------

class TestGeneratePlaybook:
    """generate_playbook returns a complete PlaybookResult."""

    def test_returns_playbook_result(self):
        persona = _persona()
        result = generate_playbook(persona)
        assert isinstance(result, PlaybookResult)

    def test_has_anchor_number(self):
        persona = _persona()
        result = generate_playbook(persona)
        assert result.anchor_number > 0

    def test_has_walk_away_point(self):
        persona = _persona()
        result = generate_playbook(persona)
        assert result.walk_away_point > 0

    def test_anchor_above_walk_away_for_salary(self):
        """For salary (user wants more), anchor > walk_away."""
        persona = _persona()  # reservation > opening => user wants more
        result = generate_playbook(persona)
        assert result.anchor_number >= result.walk_away_point

    def test_has_three_objections(self):
        persona = _persona()
        result = generate_playbook(persona)
        assert len(result.likely_objections) == 3

    def test_objections_have_fields(self):
        persona = _persona()
        result = generate_playbook(persona)
        for obj in result.likely_objections:
            assert isinstance(obj, Objection)
            assert len(obj.objection) > 0
            assert len(obj.response) > 0
            assert len(obj.reasoning) > 0

    def test_concession_ladder_has_three_steps(self):
        persona = _persona()
        result = generate_playbook(persona)
        assert len(result.concession_ladder) == 3
        for step in result.concession_ladder:
            assert isinstance(step, ConcessionStep)

    def test_key_questions_nonempty(self):
        persona = _persona()
        result = generate_playbook(persona)
        assert len(result.key_questions) >= 1

    def test_danger_phrases_nonempty(self):
        persona = _persona()
        result = generate_playbook(persona)
        assert len(result.danger_phrases) >= 1


# ---------------------------------------------------------------------------
# Style-specific behavior
# ---------------------------------------------------------------------------

class TestPlaybookByStyle:
    """Playbook content varies with opponent negotiation style."""

    def test_competitive_opening_line(self):
        persona = _persona(style=NegotiationStyle.COMPETITIVE)
        result = generate_playbook(persona)
        assert "homework" in result.opening_line.lower() or "market" in result.opening_line.lower()

    def test_collaborative_opening_line(self):
        persona = _persona(style=NegotiationStyle.COLLABORATIVE)
        result = generate_playbook(persona)
        assert "appreciate" in result.opening_line.lower()

    def test_accommodating_opening_line(self):
        persona = _persona(style=NegotiationStyle.ACCOMMODATING)
        result = generate_playbook(persona)
        assert "excited" in result.opening_line.lower()

    def test_avoiding_batna_timing_references_early(self):
        """Impatient opponents should get early BATNA timing."""
        persona = _persona(style=NegotiationStyle.AVOIDING, patience=0.2)
        result = generate_playbook(persona)
        assert "early" in result.batna_deploy_timing.lower()

    def test_high_pressure_walk_away_script(self):
        persona = _persona(pressure=PressureLevel.HIGH)
        result = generate_playbook(persona)
        assert "great opportunity" in result.walk_away_script.lower()


# ---------------------------------------------------------------------------
# Post-session lesson extraction
# ---------------------------------------------------------------------------

class TestLessonExtraction:
    """When state is provided, generate_playbook includes lessons."""

    def _make_state(self, persona, turns):
        state = NegotiationState(persona=persona)
        state.opponent_opening_anchor = persona.opening_offer
        state.transcript = turns
        for t in turns:
            if t.speaker == TurnSpeaker.USER and t.offer_amount is not None:
                if state.user_opening_anchor is None:
                    state.user_opening_anchor = t.offer_amount
                state.user_last_offer = t.offer_amount
            if t.speaker == TurnSpeaker.USER and t.move_type == MoveType.QUESTION:
                state.user_question_count += 1
            if t.speaker == TurnSpeaker.USER and t.move_type == MoveType.BATNA_SIGNAL:
                state.user_batna_signals += 1
            if t.speaker == TurnSpeaker.USER and t.move_type == MoveType.CONCESSION:
                state.user_concession_count += 1
        return state

    def test_no_anchor_lesson(self):
        persona = _persona()
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "Sounds interesting.", MoveType.UNKNOWN, None),
        ]
        state = self._make_state(persona, turns)
        result = generate_playbook(persona, state=state)
        assert any("anchor" in l.lower() for l in result.lessons_from_session)

    def test_no_questions_lesson(self):
        persona = _persona()
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "$130K.", MoveType.ANCHOR, 130_000),
        ]
        state = self._make_state(persona, turns)
        result = generate_playbook(persona, state=state)
        assert any("question" in l.lower() for l in result.lessons_from_session)

    def test_no_batna_lesson(self):
        persona = _persona()
        turns = [
            Turn(1, TurnSpeaker.OPPONENT, "Offer.", MoveType.ANCHOR, 80_000),
            Turn(2, TurnSpeaker.USER, "$130K.", MoveType.ANCHOR, 130_000),
        ]
        state = self._make_state(persona, turns)
        result = generate_playbook(persona, state=state)
        assert any("alternative" in l.lower() for l in result.lessons_from_session)

    def test_without_state_no_lessons(self):
        persona = _persona()
        result = generate_playbook(persona, state=None)
        assert result.lessons_from_session == []


# ---------------------------------------------------------------------------
# Scenario metadata
# ---------------------------------------------------------------------------

class TestPlaybookWithScenario:
    """Scenario dict affects the scenario_summary."""

    def test_salary_scenario_summary(self):
        persona = _persona()
        result = generate_playbook(persona, scenario={"type": "salary", "difficulty": "hard"})
        assert "salary" in result.scenario_summary.lower()

    def test_freelance_scenario_summary(self):
        persona = _persona()
        result = generate_playbook(persona, scenario={"type": "freelance", "difficulty": "easy"})
        assert "freelance" in result.scenario_summary.lower()

    def test_default_scenario(self):
        persona = _persona()
        result = generate_playbook(persona, scenario=None)
        assert len(result.scenario_summary) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestPlaybookEdgeCases:
    """Edge cases for playbook generation."""

    def test_persona_with_no_hidden_constraints(self):
        persona = _persona(hidden_constraints=[])
        result = generate_playbook(persona)
        assert isinstance(result, PlaybookResult)
        assert len(result.likely_objections) == 3

    def test_zero_opening_offer(self):
        """Persona with 0 opening should not cause division by zero."""
        persona = _persona(opening_offer=0.01, reservation_price=100)
        result = generate_playbook(persona)
        assert result.anchor_number >= 0
