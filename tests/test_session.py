"""Tests for session lifecycle management."""

import pytest

from dealsim_mvp.core.session import (
    create_session,
    negotiate,
    complete_session,
    get_transcript,
    get_session_state,
    SessionStatus,
    TurnResult,
)
from dealsim_mvp.core.simulator import MoveType, Turn, TurnSpeaker
from dealsim_mvp.core.scorer import Scorecard


class TestCreateSession:
    """create_session should return a valid session ID and opening turn."""

    def test_returns_tuple(self):
        sid, turn = create_session()
        assert isinstance(sid, str) and len(sid) > 0
        assert isinstance(turn, Turn)

    def test_opening_turn_is_opponent(self):
        _, turn = create_session()
        assert turn.speaker == TurnSpeaker.OPPONENT

    def test_opening_turn_has_text(self):
        _, turn = create_session()
        assert isinstance(turn.text, str) and len(turn.text) > 0

    def test_opening_turn_is_anchor(self):
        _, turn = create_session()
        assert turn.move_type == MoveType.ANCHOR

    def test_opening_turn_has_offer(self):
        _, turn = create_session()
        assert turn.offer_amount is not None and turn.offer_amount > 0

    def test_custom_scenario(self):
        sid, turn = create_session(
            scenario={"type": "freelance", "target_value": 100, "difficulty": "hard"}
        )
        assert isinstance(sid, str)
        assert turn.offer_amount is not None

    def test_custom_persona(self, salary_persona):
        sid, turn = create_session(persona=salary_persona)
        state = get_session_state(sid)
        assert state.persona.name == salary_persona.name

    def test_session_id_is_uuid(self):
        import uuid
        sid, _ = create_session()
        uuid.UUID(sid)  # Raises ValueError if not valid UUID


class TestNegotiate:
    """negotiate should return opponent responses and update state."""

    def test_returns_turn_result(self):
        sid, _ = create_session()
        result = negotiate(sid, "I'm looking for $130,000")
        assert isinstance(result, TurnResult)

    def test_result_has_opponent_text(self):
        sid, _ = create_session()
        result = negotiate(sid, "I'd like $130,000")
        assert isinstance(result.opponent_text, str) and len(result.opponent_text) > 0

    def test_result_has_turn_number(self):
        sid, _ = create_session()
        r1 = negotiate(sid, "I want $130K")
        assert r1.turn_number > 0

    def test_unknown_session_raises_key_error(self):
        with pytest.raises(KeyError, match="not found"):
            negotiate("nonexistent-id", "hello")

    def test_state_tracks_user_offer(self):
        sid, _ = create_session()
        negotiate(sid, "I want $130,000")
        state = get_session_state(sid)
        assert state.user_last_offer == pytest.approx(130_000)

    def test_state_tracks_questions(self):
        sid, _ = create_session()
        negotiate(sid, "What is the budget range?")
        state = get_session_state(sid)
        assert state.user_question_count == 1

    def test_state_tracks_batna(self):
        sid, _ = create_session()
        negotiate(sid, "I have another offer from a competitor")
        state = get_session_state(sid)
        assert state.user_batna_signals == 1


class TestCompleteSession:
    """complete_session should return a scorecard."""

    def test_returns_scorecard(self):
        sid, _ = create_session()
        negotiate(sid, "I want $130,000")
        sc = complete_session(sid)
        assert isinstance(sc, Scorecard)

    def test_scorecard_has_dimensions(self):
        sid, _ = create_session()
        negotiate(sid, "I want $130,000")
        sc = complete_session(sid)
        assert len(sc.dimensions) == 6

    def test_scorecard_has_overall_score(self):
        sid, _ = create_session()
        negotiate(sid, "I want $130,000")
        sc = complete_session(sid)
        assert 0 <= sc.overall <= 100

    def test_idempotent_on_repeated_calls(self):
        sid, _ = create_session()
        negotiate(sid, "I want $130,000")
        sc1 = complete_session(sid)
        sc2 = complete_session(sid)
        assert sc1.overall == sc2.overall

    def test_unknown_session_raises_key_error(self):
        with pytest.raises(KeyError):
            complete_session("nonexistent-id")


class TestCannotNegotiateOnCompletedSession:
    """Negotiating on a completed session should raise RuntimeError."""

    def test_raises_runtime_error(self):
        sid, _ = create_session()
        negotiate(sid, "I want $130,000")
        complete_session(sid)
        with pytest.raises(RuntimeError, match="cannot accept new turns"):
            negotiate(sid, "Actually, $125,000")

    def test_deal_resolved_blocks_further_negotiation(self, salary_persona):
        """When a deal is reached, session auto-completes."""
        sid, _ = create_session(persona=salary_persona)
        # Offer within reservation price (115K) -- should auto-accept
        result = negotiate(sid, "I'll take $100,000")
        if result.resolved:
            with pytest.raises(RuntimeError):
                negotiate(sid, "Wait, I changed my mind")


class TestMultipleSessionsIndependent:
    """Multiple sessions should not interfere with each other."""

    def test_two_sessions_have_different_ids(self):
        sid1, _ = create_session()
        sid2, _ = create_session()
        assert sid1 != sid2

    def test_negotiation_in_one_does_not_affect_other(self):
        sid1, _ = create_session()
        sid2, _ = create_session()
        negotiate(sid1, "I want $130,000")
        state2 = get_session_state(sid2)
        assert state2.user_last_offer is None

    def test_completing_one_does_not_complete_other(self):
        sid1, _ = create_session()
        sid2, _ = create_session()
        negotiate(sid1, "I want $130,000")
        complete_session(sid1)
        # sid2 should still be negotiable
        result = negotiate(sid2, "I want $120,000")
        assert isinstance(result, TurnResult)


class TestTranscript:
    """get_transcript should return the full ordered history."""

    def test_transcript_starts_with_opener(self):
        sid, _ = create_session()
        transcript = get_transcript(sid)
        assert len(transcript) >= 1
        assert transcript[0].speaker == TurnSpeaker.OPPONENT

    def test_transcript_grows_after_negotiate(self):
        sid, _ = create_session()
        before = len(get_transcript(sid))
        negotiate(sid, "I want $130K")
        after = len(get_transcript(sid))
        # Should add user turn + opponent turn = 2 more
        assert after == before + 2
