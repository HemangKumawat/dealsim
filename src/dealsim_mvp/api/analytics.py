"""
Extended analytics: user progress tracking, pattern detection, daily challenges.

Builds on top of the AnalyticsTracker (JSONL) to provide:
- Per-user score history across sessions
- Negotiation pattern detection
- Daily challenge state and scoring
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(os.environ.get("DEALSIM_DATA_DIR", "data"))
USER_HISTORY_FILE = _DATA_DIR / "user_history.jsonl"
CHALLENGE_SUBMISSIONS_FILE = _DATA_DIR / "challenge_submissions.jsonl"
_lock = threading.Lock()


def _ensure_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _append_jsonl(filepath: Path, record: dict) -> None:
    with _lock:
        try:
            _ensure_dir()
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception:
            logger.warning("Write failed for %s", filepath, exc_info=True)


def _read_jsonl(filepath: Path) -> list[dict]:
    if not filepath.exists():
        return []
    records: list[dict] = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        logger.warning("Read failed for %s", filepath, exc_info=True)
    return records


# ---------------------------------------------------------------------------
# User progress
# ---------------------------------------------------------------------------

@dataclass
class SessionSummary:
    """Lightweight record of a completed session for user history."""
    session_id: str
    user_id: str
    scenario_type: str
    difficulty: str
    overall_score: int
    outcome: str
    agreed_value: float | None
    opponent_name: str
    completed_at: str
    dimension_scores: dict[str, int] = field(default_factory=dict)


def record_session_for_user(summary: SessionSummary) -> None:
    """Append a session summary to user history."""
    _append_jsonl(USER_HISTORY_FILE, {
        "session_id": summary.session_id,
        "user_id": summary.user_id,
        "scenario_type": summary.scenario_type,
        "difficulty": summary.difficulty,
        "overall_score": summary.overall_score,
        "outcome": summary.outcome,
        "agreed_value": summary.agreed_value,
        "opponent_name": summary.opponent_name,
        "completed_at": summary.completed_at,
        "dimension_scores": summary.dimension_scores,
    })


def get_user_history(user_id: str) -> dict:
    """Build user history from stored session summaries."""
    all_records = _read_jsonl(USER_HISTORY_FILE)
    user_records = [r for r in all_records if r.get("user_id") == user_id]

    if not user_records:
        return {
            "user_id": user_id,
            "total_sessions": 0,
            "sessions": [],
            "average_score": 0.0,
            "best_score": 0,
            "worst_score": 0,
            "score_trend": "insufficient_data",
            "favorite_scenario": None,
        }

    scores = [r["overall_score"] for r in user_records]
    avg = sum(scores) / len(scores)

    # Trend: compare last 3 vs previous 3
    if len(scores) >= 6:
        recent = scores[-3:]
        earlier = scores[-6:-3]
        r_avg = sum(recent) / len(recent)
        e_avg = sum(earlier) / len(earlier)
        trend = "improving" if r_avg > e_avg + 5 else ("declining" if r_avg < e_avg - 5 else "stable")
    else:
        trend = "insufficient_data"

    scenario_counts = Counter(r.get("scenario_type", "salary") for r in user_records)
    favorite = scenario_counts.most_common(1)[0][0] if scenario_counts else None

    return {
        "user_id": user_id,
        "total_sessions": len(user_records),
        "sessions": user_records,
        "average_score": round(avg, 1),
        "best_score": max(scores),
        "worst_score": min(scores),
        "score_trend": trend,
        "favorite_scenario": favorite,
    }


def get_user_patterns(user_id: str) -> dict:
    """Detect negotiation patterns from user session history."""
    all_records = _read_jsonl(USER_HISTORY_FILE)
    user_records = [r for r in all_records if r.get("user_id") == user_id]

    if len(user_records) < 2:
        return {
            "user_id": user_id,
            "sessions_analyzed": len(user_records),
            "patterns": [],
            "style_profile": "Insufficient data -- complete at least 2 sessions for pattern detection.",
            "top_strength": None,
            "top_weakness": None,
        }

    patterns: list[dict] = []

    # Dimension score analysis
    dim_scores: dict[str, list[int]] = {}
    for r in user_records:
        for dim, score in r.get("dimension_scores", {}).items():
            dim_scores.setdefault(dim, []).append(score)

    top_strength: str | None = None
    top_weakness: str | None = None
    best_avg = 0.0
    worst_avg = 100.0

    for dim, scores_list in dim_scores.items():
        avg = sum(scores_list) / len(scores_list)
        if avg > best_avg:
            best_avg = avg
            top_strength = dim
        if avg < worst_avg:
            worst_avg = avg
            top_weakness = dim

        if avg >= 80:
            patterns.append({
                "name": f"Strong {dim}",
                "description": f"Consistently scores well on {dim} (avg {avg:.0f}/100).",
                "frequency": "often",
                "impact": "positive",
                "recommendation": f"Keep leveraging your {dim} skills.",
            })
        elif avg <= 35:
            patterns.append({
                "name": f"Weak {dim}",
                "description": f"Consistently low scores on {dim} (avg {avg:.0f}/100).",
                "frequency": "often",
                "impact": "negative",
                "recommendation": f"Focus your next session on improving {dim}.",
            })

    # Outcome patterns
    outcomes = [r.get("outcome", "unknown") for r in user_records]
    deal_rate = outcomes.count("deal_reached") / len(outcomes) if outcomes else 0
    if deal_rate >= 0.8:
        patterns.append({
            "name": "Deal closer",
            "description": f"Reaches a deal {deal_rate*100:.0f}% of the time.",
            "frequency": "always" if deal_rate >= 0.9 else "often",
            "impact": "positive",
            "recommendation": "Challenge yourself with harder opponents.",
        })
    elif deal_rate <= 0.3:
        patterns.append({
            "name": "Frequent walkaway",
            "description": f"Only reaches a deal {deal_rate*100:.0f}% of the time.",
            "frequency": "often",
            "impact": "negative",
            "recommendation": "Practice smaller concessions to reach more deals.",
        })

    # Style profile
    all_scores = [r["overall_score"] for r in user_records]
    overall_avg = sum(all_scores) / len(all_scores)
    if overall_avg >= 75:
        style = "Skilled negotiator -- strong across multiple dimensions."
    elif overall_avg >= 55:
        style = "Developing negotiator -- clear strengths with room to grow."
    else:
        style = "Learning negotiator -- focus on anchoring and information gathering."

    return {
        "user_id": user_id,
        "sessions_analyzed": len(user_records),
        "patterns": patterns,
        "style_profile": style,
        "top_strength": top_strength,
        "top_weakness": top_weakness,
    }


# ---------------------------------------------------------------------------
# Daily challenges
# ---------------------------------------------------------------------------

CHALLENGE_POOL = [
    {
        "id": "anchor_first",
        "title": "The Anchor Challenge",
        "description": "Your interviewer asks salary expectations. Respond with a strong anchor.",
        "scenario_prompt": "An interviewer at a tech company asks: 'What are your salary expectations for this role?'",
        "scoring_criteria": ["States a specific number", "Number is above market rate", "Provides justification"],
        "max_score": 100,
        "category": "anchoring",
    },
    {
        "id": "batna_signal",
        "title": "The Leverage Signal",
        "description": "The recruiter lowballed you. Mention your alternatives without being aggressive.",
        "scenario_prompt": "The recruiter says: 'Based on our budget, we can offer $95,000.' You know market rate is $120k and you have another offer.",
        "scoring_criteria": ["Mentions alternative without ultimatum", "Stays professional", "Redirects to value"],
        "max_score": 100,
        "category": "leverage",
    },
    {
        "id": "question_probe",
        "title": "The Deep Probe",
        "description": "Ask 3 questions that would reveal the employer's hidden constraints.",
        "scenario_prompt": "You received an offer. The hiring manager says: 'We're excited to bring you on board. Any questions?'",
        "scoring_criteria": ["Asks about budget flexibility", "Asks about timeline/urgency", "Asks about non-salary components"],
        "max_score": 100,
        "category": "information",
    },
    {
        "id": "concession_discipline",
        "title": "The Slow Retreat",
        "description": "Make exactly 3 concessions, each smaller than the last.",
        "scenario_prompt": "You asked for $140,000. The employer is at $115,000. Make three counter-offers showing decreasing concessions.",
        "scoring_criteria": ["Three distinct offers", "Each concession smaller than previous", "Final offer above $125k"],
        "max_score": 100,
        "category": "concessions",
    },
    {
        "id": "value_creation",
        "title": "The Package Deal",
        "description": "Base salary is fixed at $110k. Find 3 non-salary items to negotiate.",
        "scenario_prompt": "HR says: 'Base salary is $110,000 -- that's firm. Is there anything else we can discuss?'",
        "scoring_criteria": ["Names 3+ non-salary components", "Each component is realistic", "Frames as mutual value"],
        "max_score": 100,
        "category": "value_creation",
    },
    {
        "id": "pressure_response",
        "title": "The Pressure Test",
        "description": "The employer gives you a deadline. Respond without panicking.",
        "scenario_prompt": "The recruiter says: 'We need your answer by end of day Friday. We have other candidates waiting.'",
        "scoring_criteria": ["Does not accept immediately", "Buys time professionally", "Maintains leverage"],
        "max_score": 100,
        "category": "emotional_control",
    },
    {
        "id": "email_counter",
        "title": "The Email Counter",
        "description": "Write a 3-sentence email countering an offer of $105k when you want $125k.",
        "scenario_prompt": "You received an offer email: base $105,000, standard benefits, 15 days PTO. Write your counter.",
        "scoring_criteria": ["States specific counter-number", "Provides rationale", "Maintains enthusiasm for the role"],
        "max_score": 100,
        "category": "communication",
    },
]


def get_todays_challenge() -> dict:
    """Return today's daily challenge (deterministic per date)."""
    today = date.today().isoformat()
    idx = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(CHALLENGE_POOL)
    challenge = CHALLENGE_POOL[idx].copy()
    challenge["date"] = today
    return challenge


def submit_challenge_response(user_id: str, response_text: str) -> dict:
    """Score a challenge response and store the result."""
    import re

    challenge = get_todays_challenge()
    criteria = challenge.get("scoring_criteria", [])
    lower = response_text.lower()
    breakdown: list[dict] = []
    total = 0
    points_per = challenge.get("max_score", 100) // max(len(criteria), 1)

    for criterion in criteria:
        cl = criterion.lower()
        met = False

        if "specific number" in cl or ("states" in cl and "number" in cl):
            met = bool(re.search(r"\$?\d[\d,]*", response_text))
        elif "above market" in cl:
            nums = re.findall(r"\$?([\d,]+)", response_text)
            if nums:
                met = max(float(n.replace(",", "")) for n in nums) > 100000
        elif "justification" in cl or "rationale" in cl:
            met = any(w in lower for w in ("because", "based on", "research", "market", "experience", "data"))
        elif "professional" in cl:
            met = not any(w in lower for w in ("demand", "insist", "or else", "final"))
        elif "alternative" in cl or "mentions" in cl:
            met = any(w in lower for w in ("other", "offer", "option", "opportunity", "considering"))
        elif "question" in cl or "asks" in cl:
            met = "?" in response_text
        elif "enthusiasm" in cl:
            met = any(w in lower for w in ("excited", "thrilled", "looking forward", "eager", "great"))
        elif "concession" in cl or "smaller" in cl:
            nums = re.findall(r"\$?([\d,]+)", response_text)
            met = len(nums) >= 2
        elif "non-salary" in cl or "component" in cl:
            terms = ("bonus", "equity", "stock", "remote", "vacation", "pto", "title", "signing", "flexible")
            met = sum(1 for t in terms if t in lower) >= 2
        elif "time" in cl or "buys" in cl:
            met = any(w in lower for w in ("think", "consider", "few days", "weekend", "time"))
        elif "does not accept" in cl:
            met = not any(w in lower for w in ("accept", "deal", "agreed", "sounds good"))
        elif "leverage" in cl or "maintains" in cl:
            met = any(w in lower for w in ("other", "option", "offer", "value", "worth"))
        else:
            met = len(response_text.split()) >= 10

        score = points_per if met else 0
        total += score
        breakdown.append({"criterion": criterion, "met": met, "score": score, "max": points_per})

    total = min(total, challenge.get("max_score", 100))

    _append_jsonl(CHALLENGE_SUBMISSIONS_FILE, {
        "user_id": user_id,
        "challenge_id": challenge["id"],
        "date": challenge["date"],
        "response": response_text,
        "score": total,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"total": total, "breakdown": breakdown, "challenge": challenge}
