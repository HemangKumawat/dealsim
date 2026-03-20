"""
Post-simulation debrief engine — the "What They Were Thinking" reveal.

After a negotiation session completes, this module reconstructs the opponent's
hidden internal state at every turn, computes the money left on the table,
identifies the closest-to-deal moment, and produces a move-by-move analysis
showing what happened vs. what the optimal play would have been.

All monetary values share the same unit as the persona's opening_offer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dealsim_mvp.core.persona import NegotiationPersona, NegotiationStyle, PressureLevel
from dealsim_mvp.core.simulator import MoveType, NegotiationState, Turn, TurnSpeaker


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class MoveAnalysis:
    """Analysis of a single exchange in the negotiation."""
    turn_number: int
    speaker: str                 # "user" | "opponent"
    move_type: str               # MoveType.value
    text_summary: str            # what happened in plain language
    offer_amount: float | None
    dollar_impact: float         # how this move shifted the likely outcome (+ = good for user)
    optimal_move: str            # what the user should have done instead (user turns only)
    gap_to_reservation: float | None  # distance from opponent's reservation at this point


@dataclass
class HiddenStateSnapshot:
    """Opponent's internal state at a specific turn — invisible to the user during play."""
    turn_number: int
    current_offer: float | None
    distance_to_reservation: float   # how far from their walk-away point
    willingness_to_deal: float       # 0.0-1.0, how close to accepting
    emotional_state: str             # qualitative label
    internal_reasoning: str          # what the opponent was "thinking"


@dataclass
class DebriefResult:
    """Full post-simulation debrief returned to the session layer."""
    money_left_on_table: float           # difference between deal value and reservation price
    closest_to_deal: int                 # turn number where deal was closest to happening
    move_analysis: list[MoveAnalysis]    # per-exchange breakdown
    hidden_state_timeline: list[HiddenStateSnapshot]  # opponent's internal state at each turn
    undiscovered_constraints: list[str]  # hidden constraints the user never uncovered
    optimal_outcome: float               # best possible outcome for the user
    deal_reached: bool                   # whether the negotiation ended in agreement
    agreed_value: float | None           # final deal value (None if no deal)
    reservation_price: float             # opponent's actual walk-away point (the big reveal)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_debrief(state: NegotiationState) -> DebriefResult:
    """
    Generate the full "What They Were Thinking" debrief from a completed
    negotiation state.

    Pure function — no side effects. Safe to call multiple times on the
    same state.

    Parameters
    ----------
    state : NegotiationState
        The completed negotiation state with full transcript.

    Returns
    -------
    DebriefResult
        The complete debrief including hidden state reveals, move analysis,
        and money-left-on-table computation.
    """
    persona = state.persona
    direction = _negotiation_direction(state)

    # --- Compute hidden state timeline ---
    timeline = _build_hidden_state_timeline(state, direction)

    # --- Compute move-by-move analysis ---
    moves = _build_move_analysis(state, direction)

    # --- Find the closest-to-deal moment ---
    closest_turn = _find_closest_to_deal(timeline)

    # --- Compute optimal outcome ---
    optimal = _compute_optimal_outcome(persona, direction)

    # --- Compute money left on the table ---
    if state.resolved and state.agreed_value is not None:
        if direction == "user_wants_more":
            money_left = persona.reservation_price - state.agreed_value
        else:
            money_left = state.agreed_value - persona.reservation_price
        money_left = max(0.0, money_left)
    else:
        # DEBRIEF-01 fix: for no-deal, measure from user's last offer to
        # reservation (how close they were to a deal), not the full range.
        if state.user_last_offer is not None:
            money_left = abs(persona.reservation_price - state.user_last_offer)
        else:
            # User never made an offer — full range is the potential
            money_left = abs(persona.reservation_price - persona.opening_offer)

    # --- Identify undiscovered constraints ---
    undiscovered = _find_undiscovered_constraints(state)

    return DebriefResult(
        money_left_on_table=round(money_left, 2),
        closest_to_deal=closest_turn,
        move_analysis=moves,
        hidden_state_timeline=timeline,
        undiscovered_constraints=undiscovered,
        optimal_outcome=round(optimal, 2),
        deal_reached=state.resolved,
        agreed_value=state.agreed_value,
        reservation_price=persona.reservation_price,
    )


# ---------------------------------------------------------------------------
# Direction detection
# ---------------------------------------------------------------------------

def _negotiation_direction(state: NegotiationState) -> str:
    """
    Determine whether the user wants a higher number (salary) or lower
    number (procurement).

    Returns "user_wants_more" or "user_wants_less".
    """
    user_anchor = state.user_opening_anchor
    opp_anchor = state.opponent_opening_anchor or state.persona.opening_offer

    if user_anchor is not None and user_anchor >= opp_anchor:
        return "user_wants_more"
    if user_anchor is not None and user_anchor < opp_anchor:
        return "user_wants_less"

    # Fallback: if reservation > opening, opponent is willing to go up
    if state.persona.reservation_price > state.persona.opening_offer:
        return "user_wants_more"
    return "user_wants_less"


# ---------------------------------------------------------------------------
# Hidden state timeline
# ---------------------------------------------------------------------------

def _build_hidden_state_timeline(
    state: NegotiationState,
    direction: str,
) -> list[HiddenStateSnapshot]:
    """
    Reconstruct what the opponent was 'thinking' at each turn.

    Uses persona traits (patience, emotional_reactivity, transparency) to
    generate plausible internal state at each point in the negotiation.
    """
    persona = state.persona
    reservation = persona.reservation_price
    opening = persona.opening_offer
    full_range = abs(reservation - opening)

    timeline: list[HiddenStateSnapshot] = []
    opp_current_offer = opening

    for turn in state.transcript:
        if turn.speaker == TurnSpeaker.SYSTEM:
            continue

        # Track opponent's current position
        if turn.speaker == TurnSpeaker.OPPONENT and turn.offer_amount is not None:
            opp_current_offer = turn.offer_amount

        # Distance from reservation price
        distance = abs(reservation - opp_current_offer) if opp_current_offer is not None else full_range

        # Willingness to deal: increases as opponent moves closer to reservation
        if full_range > 0:
            progress = 1.0 - (distance / full_range)
        else:
            progress = 1.0
        willingness = min(1.0, max(0.0, progress))

        # Adjust willingness based on user behavior signals
        willingness = _adjust_willingness(willingness, turn, state, persona)

        # Emotional state label
        emotional_state = _compute_emotional_state(turn, willingness, persona)

        # Internal reasoning
        reasoning = _compute_internal_reasoning(
            turn, opp_current_offer, reservation, willingness, persona, direction,
        )

        timeline.append(HiddenStateSnapshot(
            turn_number=turn.turn_number,
            current_offer=opp_current_offer,
            distance_to_reservation=round(distance, 2),
            willingness_to_deal=round(willingness, 3),
            emotional_state=emotional_state,
            internal_reasoning=reasoning,
        ))

    return timeline


def _adjust_willingness(
    base: float,
    turn: Turn,
    state: NegotiationState,
    persona: NegotiationPersona,
) -> float:
    """Adjust willingness based on what the user just did."""
    w = base

    if turn.speaker == TurnSpeaker.USER:
        # BATNA signals increase opponent's urgency
        if turn.move_type == MoveType.BATNA_SIGNAL:
            w += 0.10 * (1.0 + persona.emotional_reactivity)

        # Good questions increase willingness (opponent feels understood)
        if turn.move_type == MoveType.QUESTION:
            w += 0.03

        # Large concessions by user increase willingness
        if turn.move_type == MoveType.CONCESSION and turn.offer_amount is not None:
            w += 0.05

        # Pressure from user (implicit in aggressive anchors)
        if turn.move_type == MoveType.ANCHOR:
            w -= 0.02 * persona.emotional_reactivity

    return min(1.0, max(0.0, w))


def _compute_emotional_state(
    turn: Turn,
    willingness: float,
    persona: NegotiationPersona,
) -> str:
    """Map the opponent's internal state to a human-readable emotion label."""
    reactivity = persona.emotional_reactivity

    if willingness > 0.85:
        return "eager to close"
    if willingness > 0.70:
        return "optimistic"
    if willingness > 0.50:
        return "engaged"

    # Lower willingness — emotional state depends on what just happened
    if turn.speaker == TurnSpeaker.USER:
        if turn.move_type == MoveType.BATNA_SIGNAL:
            if reactivity > 0.5:
                return "anxious"
            return "alert"
        if turn.move_type == MoveType.PRESSURE:
            if reactivity > 0.6:
                return "defensive"
            return "cautious"
        if turn.move_type == MoveType.ANCHOR:
            return "skeptical"

    if willingness > 0.30:
        return "guarded"
    if willingness > 0.15:
        return "frustrated"
    return "ready to walk away"


def _compute_internal_reasoning(
    turn: Turn,
    opp_offer: float | None,
    reservation: float,
    willingness: float,
    persona: NegotiationPersona,
    direction: str,
) -> str:
    """Generate the opponent's internal monologue at this turn."""
    name = persona.name.split()[0]

    if turn.speaker == TurnSpeaker.OPPONENT:
        if turn.move_type == MoveType.ACCEPTANCE:
            return f"{name} decided this was good enough to close."

        if turn.move_type == MoveType.ANCHOR:
            return (
                f"{name} opened with their standard number — testing where "
                f"the candidate would land."
            )

        if turn.move_type == MoveType.CONCESSION:
            if willingness > 0.7:
                return f"{name} is getting close to their limit and wants to close."
            return f"{name} moved to keep the negotiation alive, but has more room."

        if turn.move_type == MoveType.PRESSURE:
            return f"{name} is applying pressure to test your resolve."

        if turn.move_type == MoveType.INFORMATION_SHARE:
            if persona.transparency > 0.5:
                return f"{name} shared information to build trust and move toward a deal."
            return f"{name} revealed just enough to seem cooperative without giving away leverage."

        return f"{name} is holding position, waiting to see your next move."

    # User turns — describe the opponent's reaction
    if turn.move_type == MoveType.BATNA_SIGNAL:
        if persona.pressure == PressureLevel.HIGH:
            return (
                f"{name} is worried — they need this deal and your alternatives "
                f"are a real threat."
            )
        return f"{name} noted your alternative but isn't panicking yet."

    if turn.move_type == MoveType.QUESTION:
        if persona.transparency < 0.3:
            return f"{name} is being careful about what to reveal."
        return f"{name} appreciates the question — feels like a real conversation."

    if turn.move_type == MoveType.CONCESSION:
        if willingness > 0.6:
            return f"{name} is thinking 'we're getting close — just a bit more.'"
        return f"{name} sees your movement and is calculating their next counter."

    if turn.move_type == MoveType.ANCHOR:
        gap = abs((turn.offer_amount or 0) - (opp_offer or 0))
        if gap > abs(reservation - persona.opening_offer) * 0.5:
            return f"{name} thinks your opening is aggressive but isn't walking away."
        return f"{name} sees your anchor as within striking distance."

    return f"{name} is evaluating the situation."


# ---------------------------------------------------------------------------
# Move-by-move analysis
# ---------------------------------------------------------------------------

def _build_move_analysis(
    state: NegotiationState,
    direction: str,
) -> list[MoveAnalysis]:
    """
    For each turn, compute what happened, the dollar impact, and what the
    optimal move would have been.
    """
    persona = state.persona
    reservation = persona.reservation_price
    opening = persona.opening_offer
    moves: list[MoveAnalysis] = []

    # Track a running "expected outcome" to compute dollar impact per move
    # Start at the midpoint between opening positions
    user_anchor = state.user_opening_anchor
    opp_anchor = state.opponent_opening_anchor or opening

    if user_anchor is not None:
        expected_outcome = (user_anchor + opp_anchor) / 2.0
    else:
        expected_outcome = opp_anchor

    prev_expected = expected_outcome

    # DEBRIEF-02 fix: track running per-turn positions instead of reading
    # from terminal state (state.opponent_last_offer / state.user_last_offer).
    running_opp_offer = opp_anchor
    running_user_offer = user_anchor

    for turn in state.transcript:
        if turn.speaker == TurnSpeaker.SYSTEM:
            continue

        # Update running positions as we encounter offers
        if turn.offer_amount is not None:
            if turn.speaker == TurnSpeaker.OPPONENT:
                running_opp_offer = turn.offer_amount
            elif turn.speaker == TurnSpeaker.USER:
                running_user_offer = turn.offer_amount

        # Compute text summary
        summary = _summarize_turn(turn, persona)

        # Compute gap to reservation
        if turn.offer_amount is not None:
            if direction == "user_wants_more":
                gap = reservation - turn.offer_amount
            else:
                gap = turn.offer_amount - reservation
        else:
            gap = None

        # Compute dollar impact: how this move shifted the expected outcome
        dollar_impact = 0.0
        if turn.offer_amount is not None:
            if turn.speaker == TurnSpeaker.USER:
                # User offer shifts expected outcome toward average of positions
                new_expected = (turn.offer_amount + (running_opp_offer or opp_anchor)) / 2.0
            else:
                # Opponent offer shifts expected outcome
                new_expected = (turn.offer_amount + (running_user_offer or user_anchor or opp_anchor)) / 2.0

            if direction == "user_wants_more":
                dollar_impact = new_expected - prev_expected
            else:
                dollar_impact = prev_expected - new_expected

            prev_expected = new_expected

        # Compute optimal move (user turns only)
        optimal = ""
        if turn.speaker == TurnSpeaker.USER:
            optimal = _compute_optimal_move(turn, state, persona, direction, gap)

        moves.append(MoveAnalysis(
            turn_number=turn.turn_number,
            speaker=turn.speaker.value,
            move_type=turn.move_type.value,
            text_summary=summary,
            offer_amount=turn.offer_amount,
            dollar_impact=round(dollar_impact, 2),
            optimal_move=optimal,
            gap_to_reservation=round(gap, 2) if gap is not None else None,
        ))

    return moves


def _summarize_turn(turn: Turn, persona: NegotiationPersona) -> str:
    """One-line summary of what happened in this turn."""
    name = persona.name.split()[0]
    speaker = name if turn.speaker == TurnSpeaker.OPPONENT else "You"

    match turn.move_type:
        case MoveType.ANCHOR:
            if turn.offer_amount is not None:
                return f"{speaker} anchored at ${turn.offer_amount:,.0f}."
            return f"{speaker} made an opening statement."
        case MoveType.COUNTER_OFFER:
            if turn.offer_amount is not None:
                return f"{speaker} countered with ${turn.offer_amount:,.0f}."
            return f"{speaker} pushed back."
        case MoveType.CONCESSION:
            if turn.offer_amount is not None and turn.concession_from is not None:
                delta = abs(turn.offer_amount - turn.concession_from)
                return f"{speaker} conceded ${delta:,.0f} to ${turn.offer_amount:,.0f}."
            if turn.offer_amount is not None:
                return f"{speaker} moved to ${turn.offer_amount:,.0f}."
            return f"{speaker} made a concession."
        case MoveType.QUESTION:
            return f"{speaker} asked a probing question."
        case MoveType.INFORMATION_SHARE:
            return f"{speaker} shared context or reasoning."
        case MoveType.BATNA_SIGNAL:
            return f"{speaker} referenced an alternative option."
        case MoveType.PRESSURE:
            return f"{speaker} applied pressure."
        case MoveType.ACCEPTANCE:
            if turn.offer_amount is not None:
                return f"{speaker} accepted at ${turn.offer_amount:,.0f}."
            return f"{speaker} accepted the deal."
        case MoveType.REJECTION:
            return f"{speaker} rejected the proposal."
        case _:
            return f"{speaker} responded."


def _compute_optimal_move(
    turn: Turn,
    state: NegotiationState,
    persona: NegotiationPersona,
    direction: str,
    gap_to_reservation: float | None,
) -> str:
    """Describe what the user should have done at this point."""
    reservation = persona.reservation_price

    # If the user accepted when there was still room
    if turn.move_type == MoveType.ACCEPTANCE:
        if gap_to_reservation is not None and gap_to_reservation > 0:
            return (
                f"Counter instead of accepting — there was still "
                f"${gap_to_reservation:,.0f} of room to negotiate."
            )
        return "Good timing — the deal was at or near their limit."

    # If user's first move wasn't an anchor
    if turn.move_type == MoveType.UNKNOWN and state.user_opening_anchor is None:
        return "State a specific number to anchor the negotiation."

    # If user conceded too much in one step
    if turn.move_type == MoveType.CONCESSION and turn.offer_amount is not None:
        if turn.concession_from is not None:
            step = abs(turn.offer_amount - turn.concession_from)
            anchor = state.user_opening_anchor or turn.concession_from
            if anchor != 0 and step / abs(anchor) > 0.08:
                half_step = step / 2
                if direction == "user_wants_more":
                    better_offer = turn.concession_from - half_step
                else:
                    better_offer = turn.concession_from + half_step
                return (
                    f"Smaller concession — offer ${better_offer:,.0f} instead of "
                    f"${turn.offer_amount:,.0f} to preserve negotiating room."
                )
        return "Concession size was reasonable."

    # If user anchored but not aggressively enough
    if turn.move_type == MoveType.ANCHOR and turn.offer_amount is not None:
        if direction == "user_wants_more":
            optimal_anchor = reservation * 1.15
            if turn.offer_amount < optimal_anchor:
                return (
                    f"Anchor higher — ${optimal_anchor:,.0f} would have been "
                    f"defensible and closer to their real limit."
                )
        else:
            optimal_anchor = reservation * 0.85
            if turn.offer_amount > optimal_anchor:
                return (
                    f"Anchor lower — ${optimal_anchor:,.0f} would have created "
                    f"more room to negotiate."
                )
        return "Strong anchor — well positioned."

    # If user asked a question
    if turn.move_type == MoveType.QUESTION:
        return "Good move — information is leverage."

    # If user signaled BATNA
    if turn.move_type == MoveType.BATNA_SIGNAL:
        if state.user_batna_signals > 1:
            return "One BATNA mention is strongest — repeating weakens the signal."
        return "Well-timed leverage signal."

    # If user shared information
    if turn.move_type == MoveType.INFORMATION_SHARE:
        if persona.transparency < 0.3:
            return "Be careful sharing with a guarded opponent — they won't reciprocate."
        return "Sharing information with a transparent opponent builds trust."

    if turn.move_type == MoveType.COUNTER_OFFER:
        return "Counter-offer keeps the negotiation moving."

    return ""


# ---------------------------------------------------------------------------
# Closest-to-deal detection
# ---------------------------------------------------------------------------

def _find_closest_to_deal(timeline: list[HiddenStateSnapshot]) -> int:
    """Return the turn number where the opponent was most willing to accept."""
    if not timeline:
        return 0

    best = max(timeline, key=lambda s: s.willingness_to_deal)
    return best.turn_number


# ---------------------------------------------------------------------------
# Optimal outcome computation
# ---------------------------------------------------------------------------

def _compute_optimal_outcome(
    persona: NegotiationPersona,
    direction: str,
) -> float:
    """
    The best possible outcome for the user — the opponent's reservation price.

    In salary negotiations (user wants more), the optimal outcome is the
    reservation price itself. In procurement (user wants less), it's also
    the reservation price — just in the opposite direction.
    """
    return persona.reservation_price


# ---------------------------------------------------------------------------
# Undiscovered constraints
# ---------------------------------------------------------------------------

def _find_undiscovered_constraints(state: NegotiationState) -> list[str]:
    """
    Identify which hidden constraints the user never probed for.

    A constraint is 'discovered' if the user asked a question that touches
    on the same topic (keyword match against user question text).
    """
    persona = state.persona
    if not persona.hidden_constraints:
        return []

    user_questions = " ".join(
        t.text.lower() for t in state.transcript
        if t.speaker == TurnSpeaker.USER and t.move_type == MoveType.QUESTION
    )

    # Also count information-share turns where user discussed related topics
    user_info = " ".join(
        t.text.lower() for t in state.transcript
        if t.speaker == TurnSpeaker.USER and t.move_type == MoveType.INFORMATION_SHARE
    )
    all_user_probing = user_questions + " " + user_info

    # Keyword extraction from constraints — simple but effective
    _TOPIC_KEYWORDS = {
        "board": ["board", "approval", "approved"],
        "budget": ["budget", "ceiling", "maximum", "afford", "pay"],
        "timeline": ["timeline", "deadline", "q2", "q3", "q4", "quarter", "month", "urgent"],
        "candidate": ["candidate", "previous", "rejected", "quit", "turnover"],
        "bonus": ["bonus", "signing", "sign-on"],
        "relocation": ["relocation", "moving", "move"],
        "pay_band": ["band", "pay band", "range", "grade"],
        "equity": ["equity", "stock", "options", "shares"],
        "remote": ["remote", "hybrid", "wfh", "work from home"],
        "schedule": ["schedule", "start date", "behind", "overdue"],
        "premium": ["premium", "rush", "immediate", "urgency"],
    }

    undiscovered: list[str] = []
    for constraint in persona.hidden_constraints:
        constraint_lower = constraint.lower()
        discovered = False

        for _topic, keywords in _TOPIC_KEYWORDS.items():
            # Check if constraint relates to this topic
            if any(kw in constraint_lower for kw in keywords):
                # Check if user probed this topic
                if any(kw in all_user_probing for kw in keywords):
                    discovered = True
                    break

        if not discovered:
            undiscovered.append(constraint)

    return undiscovered
