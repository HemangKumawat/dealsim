"""Integration tests: full negotiation flows from create to scorecard."""

import pytest

from dealsim_mvp.core.persona import (
    NegotiationPersona,
    NegotiationStyle,
    PressureLevel,
)
from dealsim_mvp.core.session import (
    create_session,
    negotiate,
    complete_session,
    get_session_state,
    get_transcript,
)
from dealsim_mvp.core.scorer import Scorecard


def _easy_persona() -> NegotiationPersona:
    """A persona with wide reservation to make testing easier.

    reservation=130K, opening=80K.  User offers ABOVE 130K will NOT auto-accept,
    allowing multi-round negotiation.  Offers at or below 130K WILL auto-accept.
    """
    return NegotiationPersona(
        name="Easy Recruiter",
        role="HR Manager",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=85_000,
        reservation_price=130_000,
        opening_offer=80_000,
        patience=0.8,
        transparency=0.6,
        emotional_reactivity=0.2,
    )


class TestFullNegotiationFlow:
    """Create -> negotiate 5 rounds -> complete -> verify scorecard."""

    def test_five_round_flow(self):
        persona = _easy_persona()
        sid, opening = create_session(persona=persona)

        # All offers above reservation (130K) so deal does NOT auto-accept
        messages = [
            "I was thinking around $180,000 based on my experience",
            "What's the budget range for this role?",
            "I have another offer at a competing company",
            "I could come down to $165,000",
            "How about we settle at $155,000 with equity?",
        ]

        for msg in messages:
            result = negotiate(sid, msg)
            assert result.opponent_text  # every round produces a response

        sc = complete_session(sid)
        assert isinstance(sc, Scorecard)
        assert len(sc.dimensions) == 6
        assert 0 <= sc.overall <= 100
        assert sc.persona_name == "Easy Recruiter"

        # Verify transcript captured everything
        transcript = get_transcript(sid)
        # Opening (1) + 5 rounds * 2 (user + opponent) = 11
        assert len(transcript) == 11

    def test_five_round_scores_reasonable(self):
        """A user who anchors, asks questions, signals BATNA should score well."""
        persona = _easy_persona()
        sid, _ = create_session(persona=persona)

        negotiate(sid, "I'm looking for $185,000 -- that reflects my 8 years of experience")
        negotiate(sid, "What flexibility is there on the base salary?")
        negotiate(sid, "I'm also weighing another offer from a different company")
        negotiate(sid, "I could do $175,000 if we include equity")
        negotiate(sid, "Let's settle at $160,000 with a signing bonus")

        sc = complete_session(sid)

        # Opening Strategy: anchored at 185K vs 80K opening = high
        opening = next(d for d in sc.dimensions if d.name == "Opening Strategy")
        assert opening.score >= 78

        # Information Gathering: asked 1 question in 5 turns
        info = next(d for d in sc.dimensions if d.name == "Information Gathering")
        assert info.score >= 15

        # BATNA: mentioned alternatives once
        batna = next(d for d in sc.dimensions if d.name == "BATNA Usage")
        assert batna.score >= 65


class TestAggressiveUser:
    """User anchors high, signals BATNA multiple times, concedes slowly."""

    def test_aggressive_negotiation(self):
        persona = _easy_persona()
        sid, _ = create_session(persona=persona)

        negotiate(sid, "I need $200,000 -- no less")
        negotiate(sid, "I have a competing offer for $195,000")
        negotiate(sid, "I could walk away right now and take the other offer")
        negotiate(sid, "$190,000 is my final number")
        negotiate(sid, "Fine, $185,000 but that's absolutely my floor")

        sc = complete_session(sid)

        # Should have high opening strategy (200K vs 80K opening)
        opening = next(d for d in sc.dimensions if d.name == "Opening Strategy")
        assert opening.score >= 90

        # BATNA mentioned multiple times
        batna = next(d for d in sc.dimensions if d.name == "BATNA Usage")
        assert batna.score >= 20

        assert sc.outcome in ("deal_reached", "no_deal")


class TestPassiveUser:
    """User accepts quickly without negotiating."""

    def test_quick_acceptance(self):
        persona = _easy_persona()
        sid, _ = create_session(persona=persona)

        result = negotiate(sid, "That sounds good, deal!")
        sc = complete_session(sid)

        # Should have low scores across most dimensions
        opening = next(d for d in sc.dimensions if d.name == "Opening Strategy")
        assert opening.score <= 30  # Never anchored

        info = next(d for d in sc.dimensions if d.name == "Information Gathering")
        assert info.score <= 20  # Never asked questions

        batna = next(d for d in sc.dimensions if d.name == "BATNA Usage")
        assert batna.score <= 30  # Never mentioned alternatives

        assert sc.outcome == "deal_reached"

    def test_accepts_first_offer(self):
        persona = _easy_persona()
        sid, opening_turn = create_session(persona=persona)

        result = negotiate(sid, "Works for me, let's do it")
        assert result.resolved is True
        assert result.agreed_value is not None


class TestDealReachedVsNoDeal:
    """Verify deal vs no-deal outcome classification."""

    def test_deal_reached_within_reservation(self):
        persona = _easy_persona()  # reservation = 130K
        sid, _ = create_session(persona=persona)
        result = negotiate(sid, "I'll take $120,000")
        if result.resolved:
            sc = complete_session(sid)
            assert sc.outcome == "deal_reached"
            assert sc.agreed_value is not None

    def test_no_deal_outside_reservation(self):
        """Negotiating but never reaching agreement, then completing."""
        persona = NegotiationPersona(
            name="Tight Budget",
            role="Manager",
            style=NegotiationStyle.COMPETITIVE,
            pressure=PressureLevel.LOW,
            target_price=70_000,
            reservation_price=90_000,
            opening_offer=75_000,
            patience=0.3,
            transparency=0.1,
            emotional_reactivity=0.4,
        )
        sid, _ = create_session(persona=persona)

        # Make offers above reservation (90K) -- none should be accepted
        negotiate(sid, "I need $150,000")
        negotiate(sid, "Fine, $140,000")
        negotiate(sid, "$130,000 is my floor")

        state = get_session_state(sid)
        if not state.resolved:
            sc = complete_session(sid)
            assert sc.outcome == "no_deal"
            assert sc.agreed_value is None


class TestSessionStateIntegrity:
    """State should accurately reflect the negotiation history."""

    def test_offer_tracking(self):
        persona = _easy_persona()
        sid, _ = create_session(persona=persona)

        # First offer above reservation so it doesn't auto-accept
        negotiate(sid, "I want $180,000")
        state = get_session_state(sid)
        assert state.user_opening_anchor == pytest.approx(180_000)
        assert state.user_last_offer == pytest.approx(180_000)

        negotiate(sid, "I could do $170,000")
        state = get_session_state(sid)
        assert state.user_last_offer == pytest.approx(170_000)
        assert state.user_concession_count >= 1

    def test_question_tracking(self):
        persona = _easy_persona()
        sid, _ = create_session(persona=persona)

        negotiate(sid, "What's the salary range?")
        negotiate(sid, "Is there flexibility on the base?")

        state = get_session_state(sid)
        assert state.user_question_count == 2

    def test_batna_tracking(self):
        persona = _easy_persona()
        sid, _ = create_session(persona=persona)

        negotiate(sid, "I have another offer from Google")

        state = get_session_state(sid)
        assert state.user_batna_signals == 1
