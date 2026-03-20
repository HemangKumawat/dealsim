"""
Personalized negotiation playbook generator.

Produces a printable prep document for a negotiation scenario: opening line,
anchor with justification, predicted objections with rebuttals, walk-away
point, BATNA deployment timing, concession strategy, key questions, and
danger phrases.

When called after a completed session, the playbook incorporates lessons
from the user's actual performance (via the NegotiationState transcript).
When called before a session (state is None), it generates a pure prep
document from the scenario and persona alone.

All monetary values share the same unit as the persona's opening_offer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dealsim_mvp.core.persona import NegotiationPersona, NegotiationStyle, PressureLevel
from dealsim_mvp.core.simulator import MoveType, NegotiationState, TurnSpeaker


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class Objection:
    """A predicted objection from the opponent and a scripted response."""
    objection: str       # what they will say
    response: str        # your scripted comeback
    reasoning: str       # why this works


@dataclass
class ConcessionStep:
    """One planned step in the concession ladder."""
    order: int                # 1, 2, 3 ...
    item: str                 # what you're giving up
    value_to_them: str        # why it matters to the opponent
    cost_to_you: str          # what it actually costs you
    condition: str            # what you ask for in return


@dataclass
class PlaybookResult:
    """Complete negotiation prep document."""
    # Framing
    scenario_summary: str            # one-paragraph situation description
    opponent_profile: str            # what you're dealing with

    # Opening
    opening_line: str                # exact words to say first
    anchor_number: float             # your first number
    anchor_justification: str        # why this number is defensible

    # Defense
    likely_objections: list[Objection]  # top 3 objections + responses

    # Limits
    walk_away_point: float           # your minimum acceptable outcome
    walk_away_script: str            # exact words when you walk away

    # Leverage
    batna_statement: str             # how to mention your alternative
    batna_deploy_timing: str         # when to drop the BATNA card

    # Concession strategy
    concession_ladder: list[ConcessionStep]  # what to trade, in what order
    max_total_concession: float      # total you should give up at most

    # Intelligence
    key_questions: list[str]         # questions that unlock hidden info
    danger_phrases: list[str]        # phrases to avoid at all costs

    # Post-session additions (only populated after a completed negotiation)
    lessons_from_session: list[str]  # what the user learned the hard way


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_playbook(
    persona: NegotiationPersona,
    scenario: dict | None = None,
    state: NegotiationState | None = None,
    *,
    is_pre_session: bool = False,
) -> PlaybookResult:
    """
    Generate a personalized negotiation playbook.

    Parameters
    ----------
    persona : NegotiationPersona
        The opponent's profile (known or inferred).
    scenario : dict, optional
        Scenario metadata with keys like ``type``, ``target_value``,
        ``difficulty``. Used for framing the summary.
    state : NegotiationState, optional
        If provided (post-session), the playbook incorporates lessons
        from the user's actual performance.

    Returns
    -------
    PlaybookResult
        A complete, printable negotiation prep document.
    """
    scenario = scenario or {}
    direction = _detect_direction(persona)
    target = scenario.get("target_value", persona.target_price)

    # --- Compute anchor ---
    anchor = _compute_anchor(persona, direction, target)

    # --- Walk-away point ---
    walk_away = _compute_walk_away(persona, direction, target)

    # --- Concession budget ---
    max_concession = abs(anchor - walk_away) * 0.6

    return PlaybookResult(
        scenario_summary=_build_scenario_summary(persona, scenario, is_pre_session=is_pre_session),
        opponent_profile=_build_opponent_profile(persona),
        opening_line=_build_opening_line(persona, anchor, direction),
        anchor_number=round(anchor, 2),
        anchor_justification=_build_anchor_justification(persona, anchor, direction),
        likely_objections=_build_objections(persona, anchor, direction),
        walk_away_point=round(walk_away, 2),
        walk_away_script=_build_walk_away_script(persona),
        batna_statement=_build_batna_statement(persona, direction),
        batna_deploy_timing=_build_batna_timing(persona),
        concession_ladder=_build_concession_ladder(persona, anchor, walk_away, direction),
        max_total_concession=round(max_concession, 2),
        key_questions=_build_key_questions(persona),
        danger_phrases=_build_danger_phrases(persona, direction),
        lessons_from_session=_extract_lessons(state) if state else [],
    )


# ---------------------------------------------------------------------------
# Direction detection
# ---------------------------------------------------------------------------

def _detect_direction(persona: NegotiationPersona) -> str:
    """
    "user_wants_more" = salary/rate scenario (user pushes number up).
    "user_wants_less" = procurement (user pushes number down).
    """
    if persona.reservation_price > persona.opening_offer:
        return "user_wants_more"
    return "user_wants_less"


# ---------------------------------------------------------------------------
# Anchor computation
# ---------------------------------------------------------------------------

def _compute_anchor(
    persona: NegotiationPersona,
    direction: str,
    target: float,
) -> float:
    """
    Compute the optimal opening anchor.

    Strategy: anchor 15-25% beyond the opponent's likely reservation price
    to create negotiating room while remaining defensible.
    """
    reservation = persona.reservation_price

    if direction == "user_wants_more":
        # Salary: anchor above reservation by 15-20%
        if persona.style == NegotiationStyle.COMPETITIVE:
            # Against competitive opponents, anchor more aggressively
            anchor = reservation * 1.20
        elif persona.style == NegotiationStyle.ACCOMMODATING:
            # Accommodating opponents fold easily — moderate anchor
            anchor = reservation * 1.10
        else:
            anchor = reservation * 1.15
    else:
        # Procurement: anchor below reservation by 15-20%
        if persona.style == NegotiationStyle.COMPETITIVE:
            anchor = reservation * 0.80
        elif persona.style == NegotiationStyle.ACCOMMODATING:
            anchor = reservation * 0.90
        else:
            anchor = reservation * 0.85

    return _round_to_clean(anchor, persona.opening_offer)


def _round_to_clean(value: float, reference: float) -> float:
    """Round to a psychologically clean number based on magnitude."""
    if reference >= 10_000:
        return round(value / 1000) * 1000
    if reference >= 1_000:
        return round(value / 100) * 100
    if reference >= 100:
        return round(value / 5) * 5
    return round(value, 2)


# ---------------------------------------------------------------------------
# Walk-away computation
# ---------------------------------------------------------------------------

def _compute_walk_away(
    persona: NegotiationPersona,
    direction: str,
    target: float,
) -> float:
    """
    User's walk-away point — the worst deal they should accept.

    This is NOT the opponent's reservation; it's the user's minimum
    acceptable outcome. Set slightly above the opponent's opening to
    ensure the user always improves on the first offer.
    """
    opening = persona.opening_offer
    reservation = persona.reservation_price
    midpoint = (opening + reservation) / 2.0

    if direction == "user_wants_more":
        # Accept nothing below the midpoint between their opening and reservation
        walk_away = midpoint
    else:
        walk_away = midpoint

    return _round_to_clean(walk_away, opening)


# ---------------------------------------------------------------------------
# Scenario and opponent profile
# ---------------------------------------------------------------------------

def _build_scenario_summary(
    persona: NegotiationPersona,
    scenario: dict,
    *,
    is_pre_session: bool = False,
) -> str:
    """One-paragraph description of the negotiation situation."""
    scenario_type = scenario.get("type", "salary")
    difficulty = scenario.get("difficulty", "medium")

    # PLAY-01 partial fix: cover all 10 scenario types
    type_desc = {
        "salary": "a salary negotiation",
        "freelance": "a freelance rate negotiation",
        "rent": "a rent negotiation",
        "medical_bill": "a medical bill negotiation",
        "car_buying": "a car buying negotiation",
        "scope_creep": "a scope-creep negotiation over additional project work",
        "raise": "a raise request negotiation",
        "vendor": "a vendor contract negotiation",
        "counter_offer": "a job-offer counter-negotiation",
        "budget_request": "an internal budget request negotiation",
    }.get(scenario_type, "a negotiation")

    diff_desc = {
        "easy": "relatively cooperative",
        "medium": "moderately challenging",
        "hard": "highly competitive",
    }.get(difficulty, "moderately challenging")

    # DEBRIEF-03 fix: in pre-session playbooks, do NOT reveal exact reservation.
    # Use a range estimate instead.
    if is_pre_session:
        return (
            f"You're entering {type_desc} with {persona.name}, {persona.role}. "
            f"This is expected to be {diff_desc}. They opened at "
            f"${persona.opening_offer:,.0f}. Based on typical patterns, their "
            f"walk-away point is likely 10-20% beyond their opening."
        )

    return (
        f"You're entering {type_desc} with {persona.name}, {persona.role}. "
        f"This is expected to be {diff_desc}. They opened at "
        f"${persona.opening_offer:,.0f}, but their actual walk-away point is "
        f"${persona.reservation_price:,.0f} — meaning there's "
        f"${abs(persona.reservation_price - persona.opening_offer):,.0f} of "
        f"negotiating room available."
    )


def _build_opponent_profile(persona: NegotiationPersona) -> str:
    """Characterize the opponent in actionable terms."""
    style_desc = {
        NegotiationStyle.COMPETITIVE:
            "a hard bargainer who views negotiation as win-lose. "
            "Expect pushback on every point. Don't take it personally — it's their style.",
        NegotiationStyle.COLLABORATIVE:
            "a problem-solver who wants a deal that works for both sides. "
            "Reward openness with openness, but don't over-share your constraints.",
        NegotiationStyle.ACCOMMODATING:
            "someone who wants to please. They'll concede quickly if you hold firm. "
            "Don't exploit this — push for fair value but maintain the relationship.",
        NegotiationStyle.AVOIDING:
            "a deflector who avoids committing to numbers. Pin them down with "
            "specific questions and don't let them change the subject.",
        NegotiationStyle.COMPROMISING:
            "a splitter who always goes for the midpoint. Anchor high because "
            "the 'compromise' will land halfway between your positions.",
    }

    patience_desc = (
        "They're patient — don't rush." if persona.patience > 0.6
        else "They're impatient — use silence to your advantage."
    )

    pressure_desc = {
        PressureLevel.LOW: "They have low urgency and can walk away easily.",
        PressureLevel.MEDIUM: "They have moderate pressure to close — look for time-based leverage.",
        PressureLevel.HIGH: "They NEED this deal. Use this — but subtly.",
    }[persona.pressure]

    style_text = style_desc.get(persona.style, "a standard negotiator.")

    return f"{persona.name} is {style_text} {patience_desc} {pressure_desc}"


# ---------------------------------------------------------------------------
# Opening line
# ---------------------------------------------------------------------------

def _build_opening_line(
    persona: NegotiationPersona,
    anchor: float,
    direction: str,
) -> str:
    """Exact words to open the negotiation."""
    if persona.style == NegotiationStyle.COLLABORATIVE:
        return (
            f"I appreciate you starting this conversation. Based on my research "
            f"and what I bring to the table, I'm targeting ${anchor:,.0f}. "
            f"I'd love to hear how that fits with what you're working with."
        )

    if persona.style == NegotiationStyle.COMPETITIVE:
        return (
            f"Thanks for meeting. I've done my homework on the market, and "
            f"the number that makes sense for me is ${anchor:,.0f}. "
            f"Here's why that's justified."
        )

    if persona.style == NegotiationStyle.ACCOMMODATING:
        return (
            f"I'm excited about this opportunity. Based on the value I'll deliver, "
            f"I'm looking at ${anchor:,.0f}. What does your budget look like?"
        )

    if persona.style == NegotiationStyle.AVOIDING:
        return (
            f"Before we talk numbers, I want to understand the full picture — "
            f"but to set a reference point, I'm thinking ${anchor:,.0f}. "
            f"Can you tell me about the budget range?"
        )

    # COMPROMISING
    return (
        f"I know we both want to find fair middle ground. My starting point "
        f"is ${anchor:,.0f} based on market data. Where are you starting?"
    )


# ---------------------------------------------------------------------------
# Anchor justification
# ---------------------------------------------------------------------------

def _build_anchor_justification(
    persona: NegotiationPersona,
    anchor: float,
    direction: str,
) -> str:
    """Why the anchor number is defensible."""
    opening = persona.opening_offer
    reservation = persona.reservation_price

    if direction == "user_wants_more":
        premium_pct = ((anchor / opening) - 1) * 100
        return (
            f"This anchor is {premium_pct:.0f}% above their opening offer of "
            f"${opening:,.0f}. It's defensible because: (1) it's within the range "
            f"of what they can actually pay (their real ceiling is "
            f"${reservation:,.0f}), (2) it leaves room for 2-3 concession steps "
            f"while still landing above the midpoint, and (3) research shows the "
            f"first number anchors the entire negotiation — higher anchors "
            f"produce higher outcomes."
        )
    else:
        discount_pct = (1 - (anchor / opening)) * 100
        return (
            f"This anchor is {discount_pct:.0f}% below their opening of "
            f"${opening:,.0f}. It creates room for concessions while keeping "
            f"the final number near their actual floor of ${reservation:,.0f}."
        )


# ---------------------------------------------------------------------------
# Objections
# ---------------------------------------------------------------------------

def _build_objections(
    persona: NegotiationPersona,
    anchor: float,
    direction: str,
) -> list[Objection]:
    """Top 3 likely objections based on opponent style and constraints."""
    objections: list[Objection] = []

    # Objection 1: Budget / range pushback (universal)
    if persona.style == NegotiationStyle.COMPETITIVE:
        objections.append(Objection(
            objection="That's way above our range. We can't go anywhere near that number.",
            response=(
                "I understand it might feel like a stretch. Can you share what "
                "range you're working within? I'd rather find a number that works "
                "for both of us than guess."
            ),
            reasoning=(
                "Forces them to reveal their actual range instead of hiding behind "
                "a vague rejection. Their 'range' is usually wider than they claim."
            ),
        ))
    else:
        objections.append(Objection(
            objection="That's higher than what we budgeted for this role.",
            response=(
                "I hear you — and I want to find something that works within your "
                "budget. What if we look at the total package? Sometimes there's "
                "flexibility in areas beyond base salary."
            ),
            reasoning=(
                "Shifts the conversation from a single number to a multi-variable "
                "package, which expands the zone of possible agreement."
            ),
        ))

    # Objection 2: Based on hidden constraints
    if persona.hidden_constraints:
        constraint = persona.hidden_constraints[0]
        if "band" in constraint.lower() or "strict" in constraint.lower():
            objections.append(Objection(
                objection="We have strict pay bands. I literally can't go above a certain number.",
                response=(
                    "I respect that structure. Two questions: what is the band "
                    "maximum for this level, and is there flexibility on the level "
                    "itself? Sometimes a title adjustment unlocks a different band."
                ),
                reasoning=(
                    "Pay bands are real but not walls. Title changes, one-time "
                    "bonuses, and signing packages often bypass band constraints."
                ),
            ))
        elif "timeline" in constraint.lower() or "quickly" in constraint.lower() or "q2" in constraint.lower():
            objections.append(Objection(
                objection="We need to move quickly on this — can you give me a number today?",
                response=(
                    "I'm ready to move fast too. The number I gave you is "
                    "well-researched — I can commit today if we land there. "
                    "What would it take from your side?"
                ),
                reasoning=(
                    "Their urgency is your leverage. Matching their speed while "
                    "holding your number converts time pressure into deal pressure."
                ),
            ))
        else:
            objections.append(Objection(
                objection="That doesn't align with what we've offered other candidates.",
                response=(
                    "I appreciate the context. I'm not asking to break your internal "
                    "equity — I'm asking for fair market value for the specific skills "
                    "I bring. What did the market look like when you set those benchmarks?"
                ),
                reasoning=(
                    "Reframes from 'internal comparisons' to 'current market value', "
                    "which is almost always higher than last year's benchmarks."
                ),
            ))
    else:
        objections.append(Objection(
            objection="We've already made a generous offer.",
            response=(
                "I appreciate that, and I don't doubt the intent. I'm comparing "
                "to market data and my own alternatives — can we walk through "
                "what makes this competitive?"
            ),
            reasoning=(
                "Shifts the frame from gratitude to evidence-based comparison. "
                "You're not being ungrateful — you're being informed."
            ),
        ))

    # Objection 3: Style-specific objection
    if persona.style == NegotiationStyle.COLLABORATIVE:
        objections.append(Objection(
            objection="I want to make this work, but I need you to meet me halfway.",
            response=(
                "I want that too. Here's what I can do — I'll move on [specific item] "
                "if you can move on base. That way we're both giving something."
            ),
            reasoning=(
                "Collaborative opponents respond to reciprocal concessions. "
                "Linking your move to theirs maintains the collaborative frame."
            ),
        ))
    elif persona.style == NegotiationStyle.AVOIDING:
        objections.append(Objection(
            objection="Let me take this back to the team and get back to you.",
            response=(
                "Of course. Before you do, can we align on what the decision "
                "criteria are? I want to make sure I'm addressing the right things."
            ),
            reasoning=(
                "Avoiders use 'check with the team' to delay. Pinning down "
                "criteria gives you something concrete to anchor the next round."
            ),
        ))
    else:
        objections.append(Objection(
            objection="Other candidates are willing to accept less.",
            response=(
                "That may be true — and if cost is the only factor, they might "
                "be the right choice. But you're talking to me because of [specific "
                "value]. What would it be worth to get this right the first time?"
            ),
            reasoning=(
                "Reframes from price competition to value differentiation. "
                "The 'cost of a bad hire' argument is powerful in salary negotiations."
            ),
        ))

    return objections[:3]


# ---------------------------------------------------------------------------
# Walk-away script
# ---------------------------------------------------------------------------

def _build_walk_away_script(persona: NegotiationPersona) -> str:
    """Exact words to use when walking away."""
    if persona.pressure == PressureLevel.HIGH:
        return (
            "I've really enjoyed this conversation and I can tell this is a "
            "great opportunity. But I have to be honest — at this number, "
            "I can't make it work. I'd rather walk away on good terms than "
            "accept something I'll regret. If anything changes on your end, "
            "I'm a phone call away."
        )
    return (
        "I appreciate the time you've put into this. At this point, we're "
        "too far apart for me to say yes. I'm going to explore my other "
        "options, but I genuinely hope we can revisit this if circumstances "
        "change."
    )


# ---------------------------------------------------------------------------
# BATNA strategy
# ---------------------------------------------------------------------------

def _build_batna_statement(persona: NegotiationPersona, direction: str) -> str:
    """How to mention your alternative without bluffing."""
    if persona.style == NegotiationStyle.COMPETITIVE:
        return (
            "I should mention — I'm in conversations with another "
            "[company/client] that's in a similar range. I'd prefer to work "
            "with you, but I want to be transparent about where I stand."
        )
    return (
        "To be upfront, I am exploring other options. I'm not using that "
        "as a threat — I genuinely want to find the right fit. But it does "
        "inform my timeline."
    )


def _build_batna_timing(persona: NegotiationPersona) -> str:
    """When to deploy the BATNA card."""
    if persona.patience < 0.4:
        return (
            "Deploy early (turn 2-3). This opponent is impatient — an early "
            "BATNA signal creates urgency before they try to rush you into "
            "a low number."
        )
    if persona.pressure == PressureLevel.HIGH:
        return (
            "Deploy mid-negotiation (turn 3-4). They need this deal — your "
            "BATNA signal will land hard. Don't waste it too early."
        )
    return (
        "Deploy after their second counter-offer. Wait until they've shown "
        "their hand, then use your alternative to shift the anchor point."
    )


# ---------------------------------------------------------------------------
# Concession ladder
# ---------------------------------------------------------------------------

def _build_concession_ladder(
    persona: NegotiationPersona,
    anchor: float,
    walk_away: float,
    direction: str,
) -> list[ConcessionStep]:
    """
    Build a concession strategy with decreasing step sizes.

    The pattern: large first concession (shows good faith), then
    progressively smaller moves (signals approaching limit).
    """
    total_room = abs(anchor - walk_away)
    steps: list[ConcessionStep] = []

    # Step 1: 40% of total room
    step1_value = total_room * 0.40
    steps.append(ConcessionStep(
        order=1,
        item=f"Move ${step1_value:,.0f} from your anchor",
        value_to_them="Shows good faith and keeps negotiation moving",
        cost_to_you=f"40% of your negotiating room — still well above walk-away",
        condition="Only if they move first. Never concede unilaterally.",
    ))

    # Step 2: 25% of total room
    step2_value = total_room * 0.25
    steps.append(ConcessionStep(
        order=2,
        item=f"Move another ${step2_value:,.0f}",
        value_to_them="Signals continued flexibility",
        cost_to_you=f"Smaller than step 1 — signals you're getting closer to your limit",
        condition="Ask for something in return: signing bonus, start date, remote days.",
    ))

    # Step 3: 10% of total room (final)
    step3_value = total_room * 0.10
    steps.append(ConcessionStep(
        order=3,
        item=f"Final move of ${step3_value:,.0f} — make it clear this is your last",
        value_to_them="Closes the gap",
        cost_to_you=f"Tiny step — you're at 75% of room used, still above walk-away",
        condition="Frame as: 'This is the best I can do. Can we shake on it?'",
    ))

    return steps


# ---------------------------------------------------------------------------
# Key questions
# ---------------------------------------------------------------------------

def _build_key_questions(persona: NegotiationPersona) -> list[str]:
    """Questions that unlock hidden information from this specific opponent."""
    questions: list[str] = []

    # Universal opener
    questions.append(
        "What does the full compensation package look like beyond base salary?"
    )

    # Transparency-dependent
    if persona.transparency > 0.4:
        questions.append(
            "Can you share the approved range for this role? I want to make "
            "sure I'm calibrating to your reality, not just the market."
        )
    else:
        questions.append(
            "Is there flexibility in the base, or is the room more in other "
            "parts of the package?"
        )

    # Pressure-dependent
    if persona.pressure == PressureLevel.HIGH:
        questions.append(
            "What's your timeline for filling this position? I want to make "
            "sure my decision process aligns with yours."
        )
    elif persona.pressure == PressureLevel.MEDIUM:
        questions.append(
            "How does this role fit into your team's plans for the next quarter?"
        )

    # Constraint-specific questions
    for constraint in persona.hidden_constraints[:2]:
        lower = constraint.lower()
        if "board" in lower or "approved" in lower:
            questions.append(
                "Has leadership already signed off on the budget for this hire, "
                "or is there still flexibility?"
            )
        elif "candidate" in lower or "rejected" in lower or "quit" in lower:
            questions.append(
                "Have you been looking for this role for a while? What happened "
                "with the last candidate?"
            )
        elif "bonus" in lower or "signing" in lower:
            questions.append(
                "Is a signing bonus something that's been offered for this level before?"
            )
        elif "relocation" in lower:
            questions.append(
                "Is relocation support handled separately from the base offer?"
            )

    # Cap at 6 unique questions
    seen: set[str] = set()
    unique: list[str] = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique[:6]


# ---------------------------------------------------------------------------
# Danger phrases
# ---------------------------------------------------------------------------

def _build_danger_phrases(persona: NegotiationPersona, direction: str) -> list[str]:
    """Phrases the user should never say in this negotiation."""
    phrases = [
        "I'll take whatever you can offer.",
        "That's my final offer.  (Never say 'final' unless you mean it — "
        "it eliminates all future movement.)",
        "I really need this job.  (Destroys your leverage instantly.)",
        "What's the most you can pay?  (Invites their lowest 'maximum' — "
        "anchor first instead.)",
    ]

    if persona.style == NegotiationStyle.COMPETITIVE:
        phrases.append(
            "I'm flexible on the number.  (A competitive opponent reads "
            "this as 'I'll fold under pressure.')"
        )

    if persona.style == NegotiationStyle.COLLABORATIVE:
        phrases.append(
            "I don't want to be difficult.  (Undermines your right to "
            "negotiate — you're not being difficult, you're being prepared.)"
        )

    if persona.style == NegotiationStyle.AVOIDING:
        phrases.append(
            "Take your time deciding.  (An avoider will take ALL the time. "
            "Set a gentle deadline instead.)"
        )

    if direction == "user_wants_more":
        phrases.append(
            "I'm currently making $X.  (Never anchor to your current salary — "
            "anchor to your market value.)"
        )
    else:
        phrases.append(
            "Our budget is $X.  (Never reveal your real ceiling — "
            "let them discover it through negotiation.)"
        )

    return phrases[:7]


# ---------------------------------------------------------------------------
# Post-session lesson extraction
# ---------------------------------------------------------------------------

def _extract_lessons(state: NegotiationState) -> list[str]:
    """
    Analyze a completed session and extract concrete lessons.

    Only called when state is provided (post-session playbook).
    """
    lessons: list[str] = []
    persona = state.persona

    # Lesson: Did the user anchor first?
    if state.user_opening_anchor is None:
        lessons.append(
            "You didn't anchor first. The opponent set the frame — next time, "
            "state your number before they state theirs."
        )

    # Lesson: Anchor strength
    if state.user_opening_anchor is not None:
        opp_open = state.opponent_opening_anchor or persona.opening_offer
        if state.user_opening_anchor <= opp_open:
            lessons.append(
                f"Your anchor (${state.user_opening_anchor:,.0f}) was at or below "
                f"their opening (${opp_open:,.0f}). You left money on the table "
                f"before the negotiation even started."
            )

    # Lesson: Question count
    if state.user_question_count == 0:
        lessons.append(
            "You asked zero questions. Information is leverage — even one "
            "question about budget flexibility could have unlocked hidden room."
        )

    # Lesson: BATNA usage
    if state.user_batna_signals == 0:
        lessons.append(
            "You never mentioned an alternative. Without a credible walk-away, "
            "the opponent had no reason to improve their offer."
        )
    elif state.user_batna_signals > 2:
        lessons.append(
            f"You mentioned alternatives {state.user_batna_signals} times. "
            f"Once is credible; repeating it sounds like a bluff."
        )

    # Lesson: Concession pattern
    if state.user_concession_count > 0:
        user_offers = [
            t.offer_amount for t in state.transcript
            if t.speaker == TurnSpeaker.USER and t.offer_amount is not None
        ]
        if len(user_offers) >= 3:
            steps = [abs(user_offers[i] - user_offers[i - 1]) for i in range(1, len(user_offers))]
            if len(steps) >= 2 and steps[-1] > steps[0]:
                lessons.append(
                    "Your concessions got LARGER over time instead of smaller. "
                    "This signals desperation. Plan your steps in advance: "
                    "big first, then progressively smaller."
                )

    # Lesson: Emotional capitulation
    prev_opp_move = None
    for turn in state.transcript:
        if turn.speaker == TurnSpeaker.OPPONENT:
            prev_opp_move = turn.move_type
        elif turn.speaker == TurnSpeaker.USER:
            if (turn.move_type == MoveType.ACCEPTANCE
                    and prev_opp_move == MoveType.PRESSURE):
                lessons.append(
                    "You accepted right after the opponent applied pressure. "
                    "Next time, pause — say 'Let me think about that' — then "
                    "counter instead of caving."
                )
                break

    # Lesson: Deal vs. reservation
    if state.resolved and state.agreed_value is not None:
        gap = abs(persona.reservation_price - state.agreed_value)
        if gap > abs(persona.reservation_price - persona.opening_offer) * 0.3:
            lessons.append(
                f"The deal landed at ${state.agreed_value:,.0f}, but their "
                f"walk-away was ${persona.reservation_price:,.0f}. You left "
                f"${gap:,.0f} on the table."
            )

    return lessons
