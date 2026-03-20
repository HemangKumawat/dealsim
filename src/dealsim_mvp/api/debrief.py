"""
Debrief and playbook generation for completed negotiation sessions.

Analyses the full session transcript against the opponent's hidden state
to produce move-by-move commentary, money-left-on-table calculations,
and a personalized negotiation playbook.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dealsim_mvp.core.persona import NegotiationPersona
from dealsim_mvp.core.simulator import (
    MoveType,
    NegotiationState,
    Turn,
    TurnSpeaker,
)


@dataclass
class MoveAnalysis:
    """Analysis of a single turn in the negotiation."""
    turn_number: int
    speaker: str
    move_type: str
    offer: float | None
    analysis: str
    strength: str  # "strong", "neutral", "weak"
    missed_opportunity: str | None = None


@dataclass
class DebriefReport:
    """Full debrief for a completed session."""
    session_id: str
    # Opponent hidden state revealed
    opponent_target: float
    opponent_reservation: float
    opponent_pressure: str
    hidden_constraints: list[str]
    # Outcome analysis
    agreed_value: float | None
    money_left_on_table: float | None
    optimal_outcome: float
    outcome_grade: str  # "excellent", "good", "fair", "poor"
    # Move-by-move
    move_analysis: list[MoveAnalysis]
    # Summary
    key_moments: list[str]
    biggest_mistake: str | None
    best_move: str | None


@dataclass
class PlaybookEntry:
    """A single recommendation in the playbook."""
    category: str
    title: str
    description: str
    priority: str  # "high", "medium", "low"


@dataclass
class Playbook:
    """Personalized negotiation playbook based on session performance."""
    session_id: str
    overall_score: int
    style_profile: str
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[PlaybookEntry]
    practice_scenarios: list[str]


def generate_debrief(state: NegotiationState, session_id: str) -> DebriefReport:
    """Generate a full debrief report for a completed negotiation session."""
    persona = state.persona

    # Calculate money left on table
    optimal = persona.reservation_price
    agreed = state.agreed_value
    money_left: float | None = None
    if agreed is not None:
        user_anchor = state.user_opening_anchor or agreed
        opp_anchor = state.opponent_opening_anchor or persona.opening_offer
        if user_anchor >= opp_anchor:
            # Salary: user wants more, reservation is max employer pays
            money_left = max(0.0, optimal - agreed)
        else:
            # Procurement: user wants less, reservation is min seller accepts
            money_left = max(0.0, agreed - optimal)

    # Grade the outcome
    if money_left is None:
        outcome_grade = "incomplete"
    elif money_left == 0:
        outcome_grade = "excellent"
    elif optimal != 0 and money_left / abs(optimal) < 0.05:
        outcome_grade = "good"
    elif optimal != 0 and money_left / abs(optimal) < 0.15:
        outcome_grade = "fair"
    else:
        outcome_grade = "poor"

    # Analyse each move
    moves = _analyse_moves(state)

    # Extract key moments
    key_moments = []
    best_move: str | None = None
    worst_move: str | None = None

    strong_moves = [m for m in moves if m.strength == "strong"]
    weak_moves = [m for m in moves if m.strength == "weak"]

    if strong_moves:
        best = strong_moves[0]
        best_move = f"Turn {best.turn_number}: {best.analysis}"
        key_moments.append(f"Strong move at turn {best.turn_number}: {best.analysis}")

    if weak_moves:
        worst = weak_moves[0]
        worst_move = f"Turn {worst.turn_number}: {worst.analysis}"
        key_moments.append(f"Weak move at turn {worst.turn_number}: {worst.analysis}")

    missed = [m for m in moves if m.missed_opportunity]
    for m in missed[:3]:
        key_moments.append(f"Missed opportunity at turn {m.turn_number}: {m.missed_opportunity}")

    return DebriefReport(
        session_id=session_id,
        opponent_target=persona.target_price,
        opponent_reservation=persona.reservation_price,
        opponent_pressure=persona.pressure.value,
        hidden_constraints=persona.hidden_constraints,
        agreed_value=agreed,
        money_left_on_table=money_left,
        optimal_outcome=optimal,
        outcome_grade=outcome_grade,
        move_analysis=moves,
        key_moments=key_moments,
        biggest_mistake=worst_move,
        best_move=best_move,
    )


def generate_playbook(state: NegotiationState, session_id: str, overall_score: int) -> Playbook:
    """Generate a personalized negotiation playbook."""
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[PlaybookEntry] = []

    # Analyse user patterns
    if state.user_opening_anchor is not None:
        opp_open = state.opponent_opening_anchor or state.persona.opening_offer
        if state.user_opening_anchor >= opp_open:
            anchor_ratio = (state.user_opening_anchor - opp_open) / opp_open if opp_open else 0
        else:
            anchor_ratio = (opp_open - state.user_opening_anchor) / opp_open if opp_open else 0

        if anchor_ratio >= 0.15:
            strengths.append("Strong opening anchor — you frame the negotiation well.")
        else:
            weaknesses.append("Weak opening anchor — you start too close to their number.")
            recommendations.append(PlaybookEntry(
                category="anchoring",
                title="Anchor 15-25% beyond your target",
                description="Your first number sets the frame. Research shows the final outcome "
                            "is heavily influenced by the first number stated. Aim for ambitious but defensible.",
                priority="high",
            ))
    else:
        weaknesses.append("No anchor stated — the opponent framed the entire negotiation.")
        recommendations.append(PlaybookEntry(
            category="anchoring",
            title="Always state your number first",
            description="The anchoring effect is the single most powerful tool in negotiation. "
                        "Whoever sets the first number has a statistical advantage.",
            priority="high",
        ))

    if state.user_question_count >= 2:
        strengths.append("Good information gathering through questions.")
    else:
        weaknesses.append("Insufficient questioning — negotiated with limited information.")
        recommendations.append(PlaybookEntry(
            category="information",
            title="Ask at least 2 probing questions per negotiation",
            description="Questions reveal hidden budget, urgency, and flexibility. "
                        "Try: 'What flexibility exists on the base?' and 'What's the timeline pressure?'",
            priority="high",
        ))

    if state.user_batna_signals >= 1:
        strengths.append("Referenced alternatives to strengthen position.")
    else:
        weaknesses.append("No alternatives mentioned — appeared to have no leverage.")
        recommendations.append(PlaybookEntry(
            category="leverage",
            title="Signal your alternatives once",
            description="A single mention of other options shifts the power dynamic. "
                        "Even saying 'I'm evaluating a few opportunities' is enough.",
            priority="medium",
        ))

    conc_count = state.user_concession_count
    if conc_count > 0 and state.user_opening_anchor:
        avg_conc = state.user_total_concession / conc_count / abs(state.user_opening_anchor)
        if avg_conc > 0.07:
            weaknesses.append("Large concessions — gave away too much per step.")
            recommendations.append(PlaybookEntry(
                category="concessions",
                title="Use decreasing concession steps",
                description="Plan your concessions in advance: e.g., 5k, then 2k, then 1k. "
                            "Each step should be smaller than the last, signalling you are near your limit.",
                priority="high",
            ))
        else:
            strengths.append("Disciplined concession pattern.")

    if state.user_information_shares >= 1:
        strengths.append("Shared relevant information to build credibility.")

    # Style profile
    if len(strengths) >= 3:
        style_profile = "Skilled negotiator with strong fundamentals"
    elif len(strengths) >= 1:
        style_profile = "Developing negotiator with clear strengths to build on"
    else:
        style_profile = "Beginner negotiator — focus on anchoring and questioning"

    # Practice scenarios
    practice = []
    if "anchoring" in [r.category for r in recommendations]:
        practice.append("Practice anchoring: Try a salary negotiation where you must state your number first.")
    if "information" in [r.category for r in recommendations]:
        practice.append("Practice questioning: Try a freelance rate negotiation focused entirely on asking questions.")
    if "concessions" in [r.category for r in recommendations]:
        practice.append("Practice concession discipline: Try a hard-difficulty scenario and plan 3 decreasing concession steps before starting.")
    if not practice:
        practice.append("Challenge yourself: Try a hard-difficulty scenario with a competitive opponent.")
        practice.append("Try a different scenario type to broaden your negotiation range.")

    return Playbook(
        session_id=session_id,
        overall_score=overall_score,
        style_profile=style_profile,
        strengths=strengths,
        weaknesses=weaknesses,
        recommendations=recommendations,
        practice_scenarios=practice,
    )


def _analyse_moves(state: NegotiationState) -> list[MoveAnalysis]:
    """Produce per-turn analysis of the negotiation transcript."""
    persona = state.persona
    analyses: list[MoveAnalysis] = []

    for turn in state.transcript:
        strength = "neutral"
        analysis = ""
        missed: str | None = None

        if turn.speaker == TurnSpeaker.USER:
            match turn.move_type:
                case MoveType.ANCHOR:
                    opp_open = state.opponent_opening_anchor or persona.opening_offer
                    if turn.offer_amount and opp_open:
                        ratio = abs(turn.offer_amount - opp_open) / opp_open if opp_open else 0
                        if ratio >= 0.15:
                            strength = "strong"
                            analysis = f"Ambitious anchor at {ratio*100:.0f}% above opponent opening."
                        elif ratio >= 0.05:
                            strength = "neutral"
                            analysis = f"Moderate anchor at {ratio*100:.0f}% above opponent opening."
                        else:
                            strength = "weak"
                            analysis = "Anchor too close to opponent opening — limited negotiating room."
                            missed = "Could have anchored 15-25% higher to create more room."

                case MoveType.QUESTION:
                    strength = "strong"
                    analysis = "Good — asked a question to gather information."

                case MoveType.BATNA_SIGNAL:
                    strength = "strong"
                    analysis = "Referenced alternatives to build leverage."

                case MoveType.CONCESSION:
                    if turn.concession_from and turn.offer_amount:
                        step = abs(turn.offer_amount - turn.concession_from)
                        anchor = state.user_opening_anchor or turn.concession_from
                        pct = step / abs(anchor) * 100 if anchor else 0
                        if pct > 10:
                            strength = "weak"
                            analysis = f"Large concession of {pct:.0f}% — gave up too much in one step."
                            missed = "Smaller concession would have preserved more value."
                        else:
                            strength = "neutral"
                            analysis = f"Concession of {pct:.0f}% — reasonable step."

                case MoveType.ACCEPTANCE:
                    if turn.offer_amount and persona.reservation_price:
                        gap = abs(turn.offer_amount - persona.reservation_price)
                        if persona.reservation_price != 0:
                            gap_pct = gap / abs(persona.reservation_price) * 100
                        else:
                            gap_pct = 0
                        if gap_pct > 10:
                            strength = "weak"
                            analysis = f"Accepted {gap_pct:.0f}% below what was achievable."
                            missed = f"Opponent would have gone to {persona.reservation_price:.0f}."
                        else:
                            strength = "strong"
                            analysis = "Accepted near the optimal outcome."

                case MoveType.INFORMATION_SHARE:
                    strength = "neutral"
                    analysis = "Shared information to build credibility."

                case _:
                    analysis = "General statement."

        elif turn.speaker == TurnSpeaker.OPPONENT:
            match turn.move_type:
                case MoveType.PRESSURE:
                    analysis = "Opponent applied pressure — watch for emotional reaction."
                case MoveType.CONCESSION:
                    analysis = "Opponent conceded — your approach is working."
                    strength = "strong"
                case MoveType.ACCEPTANCE:
                    analysis = "Opponent accepted the deal."
                case MoveType.ANCHOR:
                    analysis = "Opponent set their opening anchor."
                case _:
                    analysis = "Opponent response."

        analyses.append(MoveAnalysis(
            turn_number=turn.turn_number,
            speaker=turn.speaker.value,
            move_type=turn.move_type.value,
            offer=turn.offer_amount,
            analysis=analysis,
            strength=strength,
            missed_opportunity=missed,
        ))

    return analyses
