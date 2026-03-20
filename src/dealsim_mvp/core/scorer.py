"""
Negotiation scorecard generator.

Analyses a completed NegotiationState and produces a structured scorecard
covering six dimensions plus an overall DealSim score and coaching tips.

Scoring philosophy:
  - Each dimension is scored 0-100 based on observable signals in the
    transcript (offer amounts, move-type counts, timing).
  - Weights are calibrated so the overall score reflects real negotiation
    research: anchoring and concession discipline matter most.
  - Tips are generated only for dimensions with score < 70, keeping feedback
    actionable rather than exhaustive.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dealsim_mvp.core.simulator import MoveType, NegotiationState, Turn, TurnSpeaker


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    name: str
    score: int            # 0-100
    weight: float         # contribution to overall score
    explanation: str      # one-sentence rationale shown to user
    tips: list[str] = field(default_factory=list)


@dataclass
class Scorecard:
    """Full negotiation scorecard returned to the session layer."""
    session_id: str
    overall: int                        # 0-100 weighted average
    dimensions: list[DimensionScore]
    top_tips: list[str]                 # top 3 coaching tips across all dimensions
    outcome: str                        # "deal_reached" | "no_deal" | "incomplete"
    agreed_value: float | None
    persona_name: str


# ---------------------------------------------------------------------------
# Dimension weights (must sum to 1.0)
# ---------------------------------------------------------------------------
_WEIGHTS = {
    "Opening Strategy":    0.20,
    "Information Gathering": 0.15,
    "Concession Pattern":  0.25,
    "BATNA Usage":         0.15,
    "Emotional Control":   0.10,
    "Value Creation":      0.15,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_scorecard(state: NegotiationState, session_id: str) -> Scorecard:
    """
    Analyse ``state`` and return a Scorecard.

    This function is pure (no side effects) — safe to call multiple times.
    """
    dimensions = [
        _score_opening_strategy(state),
        _score_information_gathering(state),
        _score_concession_pattern(state),
        _score_batna_usage(state),
        _score_emotional_control(state),
        _score_value_creation(state),
    ]

    overall = int(
        sum(d.score * d.weight for d in dimensions)
    )

    # Collect tips from weakest dimensions first
    scored_with_tips = sorted(
        [d for d in dimensions if d.tips],
        key=lambda d: d.score,
    )
    top_tips: list[str] = []
    for d in scored_with_tips:
        top_tips.extend(d.tips)
        if len(top_tips) >= 3:
            break
    top_tips = top_tips[:3]

    outcome = (
        "deal_reached" if state.resolved
        else ("incomplete" if state.turn_count < 2 else "no_deal")
    )

    return Scorecard(
        session_id=session_id,
        overall=overall,
        dimensions=dimensions,
        top_tips=top_tips,
        outcome=outcome,
        agreed_value=state.agreed_value,
        persona_name=state.persona.name,
    )


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------

def _user_turns(state: NegotiationState) -> list[Turn]:
    return [t for t in state.transcript if t.speaker == TurnSpeaker.USER]


def _score_opening_strategy(state: NegotiationState) -> DimensionScore:
    """
    Did the user anchor first, and was the anchor ambitious?

    Anchoring first captures framing power.  An anchor > 10% above the
    opponent's opening is considered ambitious.  An anchor <= opponent's
    opening scores low (left value on the table).
    """
    name   = "Opening Strategy"
    weight = _WEIGHTS[name]

    anchor = state.user_opening_anchor
    opp    = state.opponent_opening_anchor or state.persona.opening_offer

    if anchor is None:
        return DimensionScore(
            name=name, score=20, weight=weight,
            explanation="You never stated a number — the opponent framed the entire negotiation.",
            tips=[
                "Always anchor first. The first number disproportionately shapes the final outcome.",
                "Research the market rate before the session so your anchor is defensible.",
            ],
        )

    # How ambitious was the anchor relative to opponent's opening?
    # In salary: higher is better for user.  In procurement: lower is better.
    # We detect direction from anchor vs opp comparison.
    if anchor >= opp:
        # Salary / rate scenario: user wants more
        pct_above = (anchor - opp) / opp if opp > 0 else 0.0
        if pct_above >= 0.20:
            score = 95
            explanation = f"Strong anchor at {_pct(pct_above)} above their opening — excellent framing."
            tips = []
        elif pct_above >= 0.10:
            score = 78
            explanation = f"Solid anchor at {_pct(pct_above)} above their opening."
            tips = []
        elif pct_above >= 0.02:
            score = 55
            explanation = "Anchor was only slightly above their opening — left negotiating room on the table."
            tips = ["Anchor 15-25% above your target to leave room for concessions."]
        else:
            score = 30
            explanation = "Your anchor was at or below their opening — you ceded framing power immediately."
            tips = [
                "Your anchor should be ambitious but justifiable. Start higher and concede deliberately.",
            ]
    else:
        # Procurement: user wants to pay less
        pct_below = (opp - anchor) / opp if opp > 0 else 0.0
        if pct_below >= 0.20:
            score = 92
            explanation = f"Aggressive low anchor at {_pct(pct_below)} below their opening."
            tips = []
        elif pct_below >= 0.10:
            score = 75
            explanation = "Good low anchor — created useful gap to negotiate from."
            tips = []
        else:
            score = 45
            explanation = "Anchor was close to their opening — limited your downward room."
            tips = ["In procurement, open 20-30% below your target to create negotiating runway."]

    return DimensionScore(name=name, score=score, weight=weight,
                          explanation=explanation, tips=tips)


def _score_information_gathering(state: NegotiationState) -> DimensionScore:
    """
    Did the user ask questions to uncover the opponent's constraints?

    Questions reveal hidden information (budget ceiling, urgency, flexibility).
    0 questions = blind negotiation.  2+ questions per 5 turns is healthy.
    """
    name   = "Information Gathering"
    weight = _WEIGHTS[name]

    q_count = state.user_question_count
    turns   = max(state.turn_count, 1)
    ratio   = q_count / turns

    if q_count == 0:
        score = 15
        explanation = "You asked no questions — negotiated without probing for information."
        tips = [
            "Ask about budget range, timeline pressure, and what flexibility exists before making concessions.",
            "Questions like 'Is there flexibility on the base?' often unlock hidden budget.",
        ]
    elif ratio >= 0.4:
        score = 90
        explanation = f"Asked {q_count} questions — strong information gathering throughout."
        tips = []
    elif ratio >= 0.2:
        score = 72
        explanation = f"Asked {q_count} questions — good but could probe deeper on budget and constraints."
        tips = []
    else:
        score = 48
        explanation = f"Only {q_count} question(s) in {turns} turns — more probing needed."
        tips = ["Before making any concession, ask one question to understand their constraints."]

    return DimensionScore(name=name, score=score, weight=weight,
                          explanation=explanation, tips=tips)


def _score_concession_pattern(state: NegotiationState) -> DimensionScore:
    """
    Did the user give too much too fast?

    Scored on:
    - Average concession size as % of opening anchor (smaller = better)
    - Concession acceleration: later concessions should be smaller, not larger
    - Reciprocity: did opponent concede more or less than user?
    """
    name   = "Concession Pattern"
    weight = _WEIGHTS[name]

    anchor     = state.user_opening_anchor
    n_conc     = state.user_concession_count
    total_conc = state.user_total_concession

    if anchor is None or n_conc == 0:
        if state.resolved:
            # SCORE-01 fix: check if deal landed near opponent's opening vs reservation.
            # Accepting the first offer without conceding is NOT exceptional — it means
            # the user never negotiated. Only score 100 if the deal closed near
            # the opponent's reservation price (the user held firm and won).
            opp_opening = state.opponent_opening_anchor or state.persona.opening_offer
            reservation = state.persona.reservation_price
            agreed = state.agreed_value or opp_opening
            full_range = abs(reservation - opp_opening)
            if full_range > 0:
                # How close to reservation did the deal land? (1.0 = at reservation)
                progress = 1.0 - abs(reservation - agreed) / full_range
                progress = max(0.0, min(1.0, progress))
            else:
                progress = 0.5

            if progress >= 0.7:
                score = 95
                explanation = "Reached a deal near their limit without conceding — exceptional discipline."
            elif progress >= 0.4:
                score = 70
                explanation = "Closed without concessions, but left some room on the table."
            else:
                # Deal is near opponent's opening — user just accepted first offer
                score = 35
                explanation = (
                    "Accepted near the opening offer without negotiating — "
                    "concession discipline is irrelevant if you never pushed."
                )
            tips = []
        else:
            score = 50
            explanation = "No concessions recorded — either very early session or no numbers exchanged."
            tips = []
        return DimensionScore(name=name, score=score, weight=weight,
                              explanation=explanation, tips=tips)

    avg_pct = (total_conc / abs(anchor)) / n_conc if anchor != 0 else 0

    # Check deceleration: extract user offer amounts in order
    user_offers = [
        t.offer_amount for t in state.transcript
        if t.speaker == TurnSpeaker.USER and t.offer_amount is not None
    ]
    decelerated = _check_deceleration(user_offers)

    # Reciprocity: compare user vs opponent total concession
    opp_conc = state.opponent_total_concession
    reciprocity_ok = (opp_conc >= total_conc * 0.8) if total_conc > 0 else True

    # Score matrix
    if avg_pct <= 0.03:
        base = 88
        explanation = f"Small average concession ({_pct(avg_pct)} per step) — disciplined."
    elif avg_pct <= 0.07:
        base = 68
        explanation = f"Moderate average concession ({_pct(avg_pct)} per step)."
    else:
        base = 38
        explanation = f"Large average concession ({_pct(avg_pct)} per step) — conceded too freely."

    score = base
    tips: list[str] = []

    if not decelerated:
        score = max(score - 15, 10)
        tips.append(
            "Your concessions should get smaller over time (e.g. 5k → 2k → 1k), "
            "signalling you are near your limit."
        )

    if not reciprocity_ok and total_conc > 0:
        score = max(score - 10, 10)
        tips.append(
            "You conceded more than the opponent did. Match or beat their concession "
            "pace before moving further."
        )

    if avg_pct > 0.07:
        tips.append("Never give a large concession unprompted — link every move to a specific reason.")

    score = min(score, 100)
    return DimensionScore(name=name, score=score, weight=weight,
                          explanation=explanation, tips=tips)


def _score_batna_usage(state: NegotiationState) -> DimensionScore:
    """
    Did the user reference alternatives to strengthen their position?

    A single well-timed BATNA signal can shift the power dynamic significantly.
    """
    name   = "BATNA Usage"
    weight = _WEIGHTS[name]

    signals = state.user_batna_signals

    if signals == 0:
        score = 20
        explanation = "No alternatives mentioned — opponent had no reason to believe you could walk away."
        tips = [
            "Reference your alternatives early: 'I'm exploring a few options' resets the power balance.",
            "You don't need a real competing offer — mentioning alternatives is enough to shift leverage.",
        ]
    elif signals == 1:
        score = 80
        explanation = "Referenced alternatives once — effective leverage signal."
        tips = []
    else:
        score = 65
        explanation = "Mentioned alternatives multiple times — once is usually more credible than repeatedly."
        tips = ["Mentioning alternatives too often can come across as bluffing. One clear signal is strongest."]

    return DimensionScore(name=name, score=score, weight=weight,
                          explanation=explanation, tips=tips)


def _score_emotional_control(state: NegotiationState) -> DimensionScore:
    """
    Did the user stay professional and composed?

    This is inferred from move type patterns:
    - Rapid large concessions after a pressure move suggest emotional reaction.
    - Immediate acceptance after PRESSURE suggests capitulation.
    In MVP: heuristic based on concession size acceleration and acceptance pattern.
    """
    name   = "Emotional Control"
    weight = _WEIGHTS[name]

    # Check for rapid capitulation: user accepted right after a PRESSURE move
    capitulated = False
    prev_opp_move: MoveType | None = None
    for turn in state.transcript:
        if turn.speaker == TurnSpeaker.OPPONENT:
            prev_opp_move = turn.move_type
        elif turn.speaker == TurnSpeaker.USER:
            if (turn.move_type == MoveType.ACCEPTANCE
                    and prev_opp_move == MoveType.PRESSURE):
                capitulated = True

    # Check for panic concession: user conceded more than 15% of anchor in one step
    anchor       = state.user_opening_anchor
    panic        = False
    if anchor and anchor > 0:
        user_offers = [
            t.offer_amount for t in state.transcript
            if t.speaker == TurnSpeaker.USER and t.offer_amount is not None
        ]
        for i in range(1, len(user_offers)):
            step_pct = abs(user_offers[i] - user_offers[i - 1]) / abs(anchor)
            if step_pct > 0.15:
                panic = True

    if capitulated:
        score = 25
        explanation = "Accepted after a pressure move — emotional capitulation pattern detected."
        tips = [
            "When the opponent applies pressure (deadlines, ultimatums), pause before responding.",
            "A simple 'Let me think about that' buys time and signals composure.",
        ]
    elif panic:
        score = 45
        explanation = "One large concession suggests a reactive move rather than a deliberate one."
        tips = ["Plan your concession steps in advance so you never give away more than intended under pressure."]
    else:
        score = 85
        explanation = "Concession pattern suggests steady, composed negotiating."
        tips = []

    return DimensionScore(name=name, score=score, weight=weight,
                          explanation=explanation, tips=tips)


def _score_value_creation(state: NegotiationState) -> DimensionScore:
    """
    Did the user look for integrative solutions beyond the headline number?

    Signals: information sharing, questions about non-monetary terms,
    mentions of package components (bonus, equity, vacation, remote).
    """
    name   = "Value Creation"
    weight = _WEIGHTS[name]

    info_shares   = state.user_information_shares
    user_texts    = " ".join(
        t.text.lower() for t in state.transcript
        if t.speaker == TurnSpeaker.USER
    )
    package_terms = (
        "bonus", "equity", "stock", "remote", "vacation", "pto",
        "flexible", "signing", "relocation", "title", "scope", "budget",
        "package", "benefits", "equity", "option",
    )
    package_count = sum(1 for term in package_terms if term in user_texts)

    if package_count >= 3 or info_shares >= 2:
        score = 88
        explanation = "Explored multiple dimensions beyond the headline number — integrative thinking."
        tips = []
    elif package_count >= 1 or info_shares >= 1:
        score = 60
        explanation = "Some exploration of package terms — room to go deeper."
        tips = [
            "Every negotiation has multiple variables. Ask about equity, title, remote days, "
            "or start date to create trade space."
        ]
    else:
        score = 25
        explanation = "Negotiated on price alone — left integrative value on the table."
        tips = [
            "Ask: 'What does the full package look like?' before accepting or rejecting any number.",
            "Non-monetary items (title, remote days, equity) often cost the employer little but matter to you.",
        ]

    return DimensionScore(name=name, score=score, weight=weight,
                          explanation=explanation, tips=tips)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pct(ratio: float) -> str:
    return f"{ratio * 100:.0f}%"


def _check_deceleration(offers: list[float]) -> bool:
    """
    True if concession steps are non-increasing (each step <= prior step).
    Requires at least 3 offers to evaluate.
    """
    if len(offers) < 3:
        return True   # insufficient data — don't penalise
    steps = [abs(offers[i] - offers[i - 1]) for i in range(1, len(offers))]
    # Allow one exception (noise) — require that most steps decrease
    violations = sum(1 for i in range(1, len(steps)) if steps[i] > steps[i - 1])
    return violations <= len(steps) // 3
