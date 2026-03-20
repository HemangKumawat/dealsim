"""
Mock negotiation simulation engine.

Governs turn-by-turn opponent behavior using rule-based logic derived from the
opponent's NegotiationPersona traits.  The interface is defined as an abstract
base class (SimulatorBase) so swapping in a real LLM / MiroFish engine is a
single config change: subclass and override ``generate_response``.

Unit convention: all monetary values share the same unit as the persona's
target_price / reservation_price (no conversion is performed here).
"""

from __future__ import annotations

import re
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from dealsim_mvp.core.persona import NegotiationPersona, NegotiationStyle, PressureLevel


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

class TurnSpeaker(str, Enum):
    USER     = "user"
    OPPONENT = "opponent"
    SYSTEM   = "system"


class MoveType(str, Enum):
    """Semantic classification of a negotiation move."""
    ANCHOR            = "anchor"
    COUNTER_OFFER     = "counter_offer"
    CONCESSION        = "concession"
    INFORMATION_SHARE = "information_share"
    QUESTION          = "question"
    BATNA_SIGNAL      = "batna_signal"
    PRESSURE          = "pressure"
    ACCEPTANCE        = "acceptance"
    REJECTION         = "rejection"
    UNKNOWN           = "unknown"


@dataclass
class Turn:
    """A single exchange in the negotiation transcript."""
    turn_number: int
    speaker: TurnSpeaker
    text: str
    move_type: MoveType
    offer_amount: float | None = None
    concession_from: float | None = None


@dataclass
class NegotiationState:
    """
    Full mutable state of a running negotiation.

    Kept intentionally flat so a future LLM engine can receive it as a JSON
    context block with zero adaptation.  All monetary values share the same
    unit as the persona's opening_offer.
    """
    persona: NegotiationPersona

    user_last_offer: float | None         = None
    opponent_last_offer: float | None     = None
    user_opening_anchor: float | None     = None
    opponent_opening_anchor: float | None = None

    user_concession_count: int    = 0
    opponent_concession_count: int = 0
    user_question_count: int      = 0
    user_batna_signals: int       = 0
    user_information_shares: int  = 0

    user_total_concession: float     = 0.0
    opponent_total_concession: float = 0.0

    turn_count: int            = 0
    resolved: bool             = False
    agreed_value: float | None = None

    transcript: list[Turn] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Abstract interface — swap point for real LLM / MiroFish engine
# ---------------------------------------------------------------------------

class SimulatorBase(ABC):
    """
    Abstract negotiation simulator.

    To integrate MiroFish or any LLM backend:
      1. Subclass SimulatorBase.
      2. Override ``generate_response``.
      3. Pass your subclass instance to SessionManager.

    State tracking, transcript management, and scoring hooks stay identical.
    """

    @abstractmethod
    def generate_response(
        self,
        state: NegotiationState,
        user_text: str,
    ) -> Turn:
        """
        Produce the opponent's next turn.

        Contract:
        - Append the user Turn to ``state.transcript`` before computing reply.
        - Return a Turn for the opponent (SessionManager appends it).
        - Update ``state`` fields (offers, concession counts) in place.
        """
        ...

    def initialize_state(self, persona: NegotiationPersona) -> NegotiationState:
        """Create a fresh NegotiationState for a new session."""
        return NegotiationState(persona=persona)

    def opening_statement(self, state: NegotiationState) -> Turn:
        """
        Opponent first move (before any user input).
        Default: opponent states their opening offer.
        Override for richer LLM openers.
        """
        persona = state.persona
        offer   = persona.opening_offer
        state.opponent_last_offer     = offer
        state.opponent_opening_anchor = offer

        text = _compose_opener(persona, offer)
        turn = Turn(
            turn_number=0,
            speaker=TurnSpeaker.OPPONENT,
            text=text,
            move_type=MoveType.ANCHOR,
            offer_amount=offer,
        )
        state.transcript.append(turn)
        return turn


# ---------------------------------------------------------------------------
# Rule-based mock implementation
# ---------------------------------------------------------------------------

class RuleBasedSimulator(SimulatorBase):
    """
    Rule-based negotiation opponent — MVP engine, no LLM required.

    Per-turn decision tree:
      1. Parse user message: extract offer, classify move type.
      2. Check acceptance conditions.
      3. Compute opponent next-offer using style-specific strategy.
      4. Render natural-language response from template pool.
    """

    def generate_response(
        self,
        state: NegotiationState,
        user_text: str,
    ) -> Turn:
        persona = state.persona
        state.turn_count += 1
        turn_n = state.turn_count * 2   # user = odd, opponent = even

        # 1. Record user turn
        user_move, user_offer = _classify_user_move(user_text, state)
        user_turn = Turn(
            turn_number=turn_n - 1,
            speaker=TurnSpeaker.USER,
            text=user_text,
            move_type=user_move,
            offer_amount=user_offer,
            concession_from=(
                state.user_last_offer
                if user_move == MoveType.CONCESSION
                else None
            ),
        )
        state.transcript.append(user_turn)

        # 2. Update state
        _update_state_from_user_move(state, user_move, user_offer)

        # 3. Acceptance checks
        if user_move == MoveType.ACCEPTANCE:
            agreed = state.opponent_last_offer or persona.opening_offer
            state.resolved     = True
            state.agreed_value = agreed
            text = _compose_acceptance_response(persona, agreed)
            opp  = Turn(turn_n, TurnSpeaker.OPPONENT, text, MoveType.ACCEPTANCE, agreed)
            state.transcript.append(opp)
            return opp

        if user_offer is not None and _offer_is_acceptable(user_offer, persona, state):
            state.resolved     = True
            state.agreed_value = user_offer
            text = _compose_deal_close(persona, user_offer)
            opp  = Turn(turn_n, TurnSpeaker.OPPONENT, text, MoveType.ACCEPTANCE, user_offer)
            state.transcript.append(opp)
            return opp

        # 4. Compute next number
        new_offer, move_type = _compute_opponent_offer(state, user_move, user_offer)

        # 5. Update opponent concession tracking
        # BUG-02 fix: capture prev BEFORE mutation so Turn records correct concession_from
        prev_opponent_offer = state.opponent_last_offer
        if new_offer is not None:
            if prev_opponent_offer is not None and abs(new_offer - prev_opponent_offer) > 0.01:
                state.opponent_total_concession += abs(new_offer - prev_opponent_offer)
                state.opponent_concession_count += 1
                move_type = MoveType.CONCESSION
            state.opponent_last_offer = new_offer

        # 6. Render text — pass prev_opponent_offer so holding-firm check
        #    compares against the PREVIOUS offer, not the just-mutated one.
        text = _render_opponent_response(
            persona, state, user_move, new_offer, user_text,
            prev_opponent_offer=prev_opponent_offer,
        )

        opp = Turn(
            turn_number=turn_n,
            speaker=TurnSpeaker.OPPONENT,
            text=text,
            move_type=move_type,
            offer_amount=new_offer,
            concession_from=(
                prev_opponent_offer
                if move_type == MoveType.CONCESSION
                else None
            ),
        )
        state.transcript.append(opp)
        return opp


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_MONEY_RE = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(k)?", re.IGNORECASE)

_QUESTION_SIGNALS   = ("?", "what", "how", "why", "when", "could you", "can you",
                       "would you", "tell me", "is there", "are there")
_BATNA_SIGNALS      = ("other offer", "another offer", "competing offer", "walk away",
                       "walk-away", "alternative", "other option", "other company",
                       "other client", "different role", "different project",
                       "if this doesn't", "unless", "otherwise i'll", "otherwise i will")
_ACCEPTANCE_SIGNALS = ("deal", "accept", "agreed", "let's do it", "let's do this",
                       "works for me", "i'll take it", "i'll accept", "that works",
                       "sounds good", "you've got a deal", "we have a deal")

# Scenario types where user wants the number to go DOWN (buyer/payer scenarios)
_USER_WANTS_DOWN = frozenset({
    "medical_bill", "car_buying", "rent", "vendor", "scope_creep",
})
# Scenario types where user wants the number to go UP (seller/earner scenarios)
_USER_WANTS_UP = frozenset({
    "salary", "raise", "freelance", "counter_offer", "budget_request",
})
_INFO_SIGNALS       = ("because", "since", "given that", "my research", "market rate",
                       "my experience", "i have", "i've been")


def _extract_offer(text: str) -> float | None:
    """Pull the largest plausible monetary figure from user text."""
    matches = _MONEY_RE.findall(text)
    if not matches:
        return None
    values: list[float] = []
    for digits, suffix in matches:
        cleaned = digits.replace(",", "")
        if not cleaned:
            continue
        val = float(cleaned)
        if suffix and suffix.lower() == "k":
            val *= 1_000
        values.append(val)
    return max(values) if values else None


def _user_wants_more(state: NegotiationState) -> bool:
    """
    Determine negotiation direction from anchors or persona structure.

    Returns True if the user wants the number to go UP (salary, raise, etc.).
    Returns False if the user wants the number to go DOWN (medical bill, car, rent, vendor).
    """
    user_anchor = state.user_opening_anchor
    opp_anchor = state.opponent_opening_anchor or state.persona.opening_offer
    if user_anchor is not None:
        return user_anchor >= opp_anchor
    # Fallback: if reservation > opening, the opponent can go higher => user wants more
    return state.persona.reservation_price > state.persona.opening_offer


def _classify_user_move(
    text: str, state: NegotiationState
) -> tuple[MoveType, float | None]:
    lower = text.lower()

    # BUG-05 fix: only treat acceptance signals as acceptance when no
    # monetary offer is present in the same message.
    offer = _extract_offer(text)

    if offer is None and any(s in lower for s in _ACCEPTANCE_SIGNALS):
        return MoveType.ACCEPTANCE, state.opponent_last_offer

    if any(s in lower for s in _BATNA_SIGNALS):
        return MoveType.BATNA_SIGNAL, offer

    if any(s in lower for s in _QUESTION_SIGNALS):
        if offer is not None and "?" in text:
            return MoveType.COUNTER_OFFER, offer
        return MoveType.QUESTION, offer

    if offer is not None:
        if state.user_last_offer is None and state.user_opening_anchor is None:
            return MoveType.ANCHOR, offer

        # BUG-01 fix: direction-aware concession detection.
        # A concession is when the user moves TOWARD the opponent's position.
        if state.user_last_offer is not None:
            wants_more = _user_wants_more(state)
            if wants_more:
                # User wants number up; concession = moving down toward opponent
                is_concession = offer < state.user_last_offer
            else:
                # User wants number down; concession = moving up toward opponent
                is_concession = offer > state.user_last_offer
            if is_concession:
                return MoveType.CONCESSION, offer
        return MoveType.COUNTER_OFFER, offer

    if any(s in lower for s in _INFO_SIGNALS):
        return MoveType.INFORMATION_SHARE, None

    return MoveType.UNKNOWN, None


def _update_state_from_user_move(
    state: NegotiationState, move: MoveType, offer: float | None
) -> None:
    if offer is not None:
        if state.user_opening_anchor is None:
            state.user_opening_anchor = offer
        if state.user_last_offer is not None:
            delta = abs(offer - state.user_last_offer)
            if delta > 0.01:
                # Only count as concession if user moved TOWARD the opponent's
                # position (not away from it — that's hardening, not conceding).
                wants_more = _user_wants_more(state)
                if wants_more:
                    is_toward_opponent = offer < state.user_last_offer
                else:
                    is_toward_opponent = offer > state.user_last_offer
                if is_toward_opponent:
                    state.user_total_concession += delta
                    state.user_concession_count += 1
        state.user_last_offer = offer

    match move:
        case MoveType.QUESTION:
            state.user_question_count += 1
        case MoveType.BATNA_SIGNAL:
            state.user_batna_signals += 1
        case MoveType.INFORMATION_SHARE:
            state.user_information_shares += 1


# ---------------------------------------------------------------------------
# Opponent strategy
# ---------------------------------------------------------------------------

def _offer_is_acceptable(
    offer: float, persona: NegotiationPersona, state: NegotiationState
) -> bool:
    """
    Direction detection: user opening >= opponent opening implies salary/rate
    scenario (user wants more), so opponent accepts when offer <= reservation.
    Reversed for procurement.
    """
    user_anchor = state.user_opening_anchor or offer
    opp_anchor  = state.opponent_opening_anchor or persona.opening_offer
    if user_anchor >= opp_anchor:
        return offer <= persona.reservation_price
    return offer >= persona.reservation_price


def _compute_opponent_offer(
    state: NegotiationState, user_move: MoveType, user_offer: float | None
) -> tuple[float | None, MoveType]:
    """
    Compute the opponent's next offer.

    COMPETITIVE   - small concessions; only moves under pressure
    COLLABORATIVE - mirrors user concession ratio
    ACCOMMODATING - converges fast toward midpoint
    AVOIDING      - rarely states a number
    COMPROMISING  - always splits remaining gap
    """
    persona = state.persona
    current = state.opponent_last_offer or persona.opening_offer

    if user_move in (MoveType.QUESTION, MoveType.INFORMATION_SHARE, MoveType.UNKNOWN):
        return None, MoveType.INFORMATION_SHARE
    if user_offer is None:
        return None, MoveType.UNKNOWN

    pressure_factor = {
        PressureLevel.LOW:    0.5,
        PressureLevel.MEDIUM: 1.0,
        PressureLevel.HIGH:   1.6,
    }[persona.pressure]

    full_range     = abs(persona.reservation_price - persona.opening_offer)
    already_moved  = abs(current - persona.opening_offer)
    remaining_room = max(0.0, full_range - already_moved)

    match persona.style:
        case NegotiationStyle.COMPETITIVE:
            user_ratio = _user_concession_ratio(state)
            step = remaining_room * 0.12 * pressure_factor * (1 + user_ratio * 0.5)
            step = min(step, remaining_room * 0.25)
        case NegotiationStyle.COLLABORATIVE:
            step = abs(user_offer - current) * 0.35 * pressure_factor
        case NegotiationStyle.ACCOMMODATING:
            midpoint = (user_offer + current) / 2
            step = abs(midpoint - current) * 0.6 * pressure_factor
        case NegotiationStyle.AVOIDING:
            if random.random() < 0.4:
                return current, MoveType.COUNTER_OFFER
            step = remaining_room * 0.05 * pressure_factor
        case NegotiationStyle.COMPROMISING:
            # PERSONA-04 fix: apply pressure_factor
            step = abs(user_offer - current) * 0.5 * pressure_factor
        case _:
            step = remaining_room * 0.15

    direction = 1.0 if persona.reservation_price > persona.opening_offer else -1.0
    new_offer = current + direction * step
    if direction > 0:
        new_offer = min(new_offer, persona.reservation_price)
    else:
        new_offer = max(new_offer, persona.reservation_price)

    return _round_offer(new_offer, persona.opening_offer), MoveType.COUNTER_OFFER


def _user_concession_ratio(state: NegotiationState) -> float:
    anchor = state.user_opening_anchor
    if not anchor:
        return 0.0
    return state.user_total_concession / abs(anchor)


def _round_offer(value: float, reference: float) -> float:
    if reference >= 10_000:
        return round(value / 500) * 500
    if reference >= 1_000:
        return round(value / 50) * 50
    if reference >= 100:
        return round(value / 5) * 5
    return round(value, 2)


# ---------------------------------------------------------------------------
# Response text rendering
# ---------------------------------------------------------------------------

def _fmt(value: float) -> str:
    if value >= 1_000:
        return f"${value:,.0f}"
    return f"${value:.2f}"


def _compose_opener(persona: NegotiationPersona, offer: float) -> str:
    pools: dict[NegotiationStyle, list[str]] = {
        NegotiationStyle.COMPETITIVE: [
            f"I'll be direct — based on the role and our budget, I'm looking at "
            f"{_fmt(offer)}. That's competitive for this market.",
            f"Our standard range for this position starts at {_fmt(offer)}.",
        ],
        NegotiationStyle.COLLABORATIVE: [
            f"I want this to work for both of us. We're thinking around {_fmt(offer)} "
            f"to start — happy to talk through what would feel right for you.",
            f"My starting point is {_fmt(offer)}, but I'm open to the conversation.",
        ],
        NegotiationStyle.ACCOMMODATING: [
            f"We're offering {_fmt(offer)} — but I want to make sure you feel good "
            f"about this. What are you thinking?",
        ],
        NegotiationStyle.AVOIDING: [
            f"There are a few ranges we work within — around {_fmt(offer)} tends to "
            f"be typical. We'd need to look at the full package.",
        ],
        NegotiationStyle.COMPROMISING: [
            f"Standard for this role is {_fmt(offer)}. If we're both reasonable we "
            f"should find a number that works.",
        ],
    }
    lines = pools.get(persona.style, pools[NegotiationStyle.COLLABORATIVE])
    return random.choice(lines)


def _compose_acceptance_response(persona: NegotiationPersona, agreed: float) -> str:
    return random.choice([
        f"Great — aligned on {_fmt(agreed)}. I'll get the paperwork moving.",
        f"Sounds like a deal at {_fmt(agreed)}. Looking forward to working together.",
        f"Done. {_fmt(agreed)} it is. I'll send the formal offer letter.",
    ])


def _compose_deal_close(persona: NegotiationPersona, user_offer: float) -> str:
    return random.choice([
        f"You know what — {_fmt(user_offer)} works. Let's call it done.",
        f"I can do {_fmt(user_offer)}. We have a deal.",
        f"Alright, {_fmt(user_offer)} — I'll get sign-off today.",
    ])


def _render_opponent_response(
    persona: NegotiationPersona,
    state: NegotiationState,
    user_move: MoveType,
    new_offer: float | None,
    user_text: str,
    *,
    prev_opponent_offer: float | None = None,
) -> str:
    match user_move:
        case MoveType.QUESTION:
            preamble = _question_response(persona, user_text)
            if new_offer is None:
                return preamble
        case MoveType.BATNA_SIGNAL:
            preamble = _batna_response(persona)
        case MoveType.INFORMATION_SHARE:
            preamble = _info_share_response(persona)
            if new_offer is None:
                return preamble
        case MoveType.ANCHOR:
            preamble = _anchor_reaction(persona, state)
        case MoveType.CONCESSION:
            preamble = _concession_reaction(persona)
        case MoveType.COUNTER_OFFER:
            preamble = _counter_reaction()
        case _:
            preamble = _generic_reaction()

    if new_offer is None:
        return preamble

    # Use prev_opponent_offer (before mutation) to detect whether the opponent
    # actually moved.  Falls back to state for backward compatibility.
    baseline = prev_opponent_offer or state.opponent_last_offer or persona.opening_offer
    offer_line = (
        _holding_line(baseline)
        if abs(new_offer - baseline) < 1
        else _new_offer_line(new_offer, persona.style)
    )
    return f"{preamble} {offer_line}".strip()


def _anchor_reaction(persona: NegotiationPersona, state: NegotiationState) -> str:
    gap_pct = 0.0
    if state.user_last_offer and state.opponent_last_offer:
        avg = (state.user_last_offer + state.opponent_last_offer) / 2
        if avg > 0:
            gap_pct = abs(state.user_last_offer - state.opponent_last_offer) / avg * 100
    match persona.style:
        case NegotiationStyle.COMPETITIVE:
            return random.choice([
                "That's a significant jump from where we are.",
                f"We're roughly {gap_pct:.0f}% apart — but let's keep talking.",
                "That number is outside what we're working with.",
            ])
        case NegotiationStyle.COLLABORATIVE:
            return random.choice([
                "I hear you — let me think about how we close that gap.",
                "That's higher than I expected, but I want to find something that works.",
            ])
        case _:
            return random.choice([
                "Interesting starting point.",
                "I see where you're coming from — we're not quite there yet.",
            ])


def _concession_reaction(persona: NegotiationPersona) -> str:
    match persona.style:
        case NegotiationStyle.COLLABORATIVE:
            return random.choice([
                "I appreciate you moving on that.",
                "Good — that shows flexibility. Let me do the same.",
            ])
        case NegotiationStyle.COMPETITIVE:
            return random.choice([
                "That's a step, but we're still a ways apart.",
                "Okay, noted.",
            ])
        case _:
            return random.choice(["That helps.", "Alright, I can work with that."])


def _counter_reaction() -> str:
    return random.choice([
        "Let me see what I can do.",
        "I hear you.",
        "Fair enough — here's where I land.",
    ])


def _question_response(persona: NegotiationPersona, user_text: str) -> str:
    lower = user_text.lower()
    t     = persona.transparency

    if any(w in lower for w in ("budget", "range", "ceiling", "maximum", "afford")):
        if t > 0.6:
            return (
                f"Honestly, there's flexibility — we're working up to around "
                f"{_fmt(persona.reservation_price * 0.95)} depending on the candidate."
            )
        if t > 0.3:
            return "There's a range we work within — I can't share the exact ceiling, but there is room."
        return "I'm not really in a position to share the full budget picture."

    if any(w in lower for w in ("timeline", "when", "start", "deadline", "urgent")):
        if persona.pressure == PressureLevel.HIGH:
            return "Honestly, we need to move quickly — ideally within the month."
        return "We're working toward a Q2 start but there's some flexibility."

    if any(w in lower for w in ("flexible", "flexibility", "room", "negotiate", "move")):
        if persona.style in (NegotiationStyle.COLLABORATIVE, NegotiationStyle.ACCOMMODATING):
            return "Yes, there's room — I wouldn't be here if there wasn't."
        return "There's always some discussion to be had."

    return random.choice([
        "Good question — let me address that.",
        "Fair to ask.",
        "I can speak to that.",
    ])


def _batna_response(persona: NegotiationPersona) -> str:
    if persona.pressure == PressureLevel.HIGH:
        return random.choice([
            "I understand you have other options — let's make sure we find something that keeps you here.",
            "I'd hate to lose you over a number we can work on.",
        ])
    match persona.style:
        case NegotiationStyle.COMPETITIVE:
            return random.choice([
                "That's a strong position to be in. So is ours.",
                "Good to know. We have candidates too — but let's see if we can make this work.",
            ])
        case _:
            return random.choice([
                "I respect that you're weighing options. Let's make our offer worth choosing.",
                "Understood — I want to make sure what we put on the table is competitive.",
            ])


def _info_share_response(persona: NegotiationPersona) -> str:
    if persona.transparency > 0.5:
        return random.choice([
            "I appreciate you sharing that context — let me be equally direct.",
            "That's useful to know. Here's where we stand on our side.",
        ])
    return random.choice(["I hear you.", "That context helps.", "Understood."])


def _generic_reaction() -> str:
    return random.choice([
        "Let me think about that.",
        "Okay.",
        "I see where you're coming from.",
    ])


def _holding_line(current: float) -> str:
    return random.choice([
        f"I have to stay at {_fmt(current)} for now.",
        f"My position is {_fmt(current)} — I'm not in a place to move further today.",
    ])


def _new_offer_line(offer: float, style: NegotiationStyle) -> str:
    match style:
        case NegotiationStyle.COMPETITIVE:
            return random.choice([
                f"I can come up to {_fmt(offer)} — and that's me stretching.",
                f"Best I can do is {_fmt(offer)}.",
                f"I'll go to {_fmt(offer)}, but that's firm.",
            ])
        case NegotiationStyle.COLLABORATIVE:
            return random.choice([
                f"What if we landed at {_fmt(offer)}? I think that's fair for both sides.",
                f"I can offer {_fmt(offer)} — how does that feel?",
            ])
        case NegotiationStyle.ACCOMMODATING:
            return random.choice([
                f"What about {_fmt(offer)}? I want you to feel good about this.",
                f"How about {_fmt(offer)} — does that work for you?",
            ])
        case NegotiationStyle.AVOIDING:
            return (
                f"We might be able to look at something around {_fmt(offer)}, "
                f"depending on the full package."
            )
        case _:
            return random.choice([
                f"Split the difference — {_fmt(offer)}?",
                f"Let's meet in the middle: {_fmt(offer)}.",
            ])
