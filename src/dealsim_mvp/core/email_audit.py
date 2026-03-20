"""
Negotiation email auditor.

Analyses a draft negotiation email for common weaknesses using regex and
keyword detection — no LLM required. The patterns are drawn from negotiation
research: hedging language, missing anchors, passive voice, and structural
problems all correlate with worse outcomes.

Scoring: starts at 100, deductions per issue (severity-dependent).
A rewritten version is produced by applying mechanical fixes to the
most impactful issues.

Example
-------
>>> audit = audit_negotiation_email("Hi, I was hoping if possible to maybe get a raise.")
>>> audit.score < 60
True
>>> any(i.issue_type == "hedging" for i in audit.issues)
True
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Constants — pattern libraries
# ---------------------------------------------------------------------------

HEDGING_PHRASES: list[str] = [
    "i was hoping",
    "if possible",
    "i think maybe",
    "perhaps",
    "i was wondering if",
    "would it be possible",
    "i feel like",
    "i'm not sure but",
    "sorry to ask",
    "no worries if not",
    "just wondering",
    "i don't want to be pushy",
    "i hate to ask",
    "if it's not too much trouble",
    "i might be wrong but",
]

POWER_PHRASES: list[str] = [
    "based on my research",
    "market data shows",
    "i'd like to discuss",
    "i'm excited about",
    "the value i bring",
    "i'm confident that",
    "i've contributed",
    "my track record",
    "comparable roles pay",
    "industry benchmarks",
]

PASSIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bit\s+would\s+be\s+appreciated\b", re.IGNORECASE),
    re.compile(r"\bit\s+was\s+(suggested|recommended|mentioned)\b", re.IGNORECASE),
    re.compile(r"\bi\s+was\s+told\s+that\b", re.IGNORECASE),
    re.compile(r"\bit\s+has\s+been\s+(noted|observed)\b", re.IGNORECASE),
    re.compile(r"\bconsideration\s+would\s+be\b", re.IGNORECASE),
    re.compile(r"\bit\s+is\s+hoped\b", re.IGNORECASE),
]

EMOTIONAL_TRIGGERS: list[str] = [
    "unfair",
    "insulting",
    "disrespected",
    "deserve better",
    "i'm upset",
    "frustrated that",
    "disappointed in",
    "taken advantage of",
    "not valued",
    "i'll have to look elsewhere",
    "threatening to leave",
]

MONEY_PATTERN = re.compile(r"\$[\d,]+(?:\.\d{2})?|\d+[kK](?:\s|$)")

GRATITUDE_OPENERS: list[str] = [
    "thank you",
    "thanks for",
    "i appreciate",
    "grateful",
    "i'm excited",
    "excited about",
    "thrilled",
    "looking forward",
]

SPECIFIC_ASK_CLOSERS: list[str] = [
    "i'd like to request",
    "i'm asking for",
    "i propose",
    "my target is",
    "i'd like to discuss a salary of",
    "would you be available to",
    "can we schedule",
    "i'd appreciate a meeting",
    "let's find a time",
]


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


SEVERITY_DEDUCTIONS = {
    Severity.HIGH: 15,
    Severity.MEDIUM: 8,
    Severity.LOW: 4,
}


@dataclass
class Issue:
    """A single problem found in the email."""
    severity: Severity
    location: str           # e.g. "paragraph 2", "opening", "closing"
    issue_type: str         # e.g. "hedging", "passive_voice"
    issue: str              # human-readable description
    suggestion: str         # concrete rewrite or advice


@dataclass
class EmailAudit:
    """Full audit result for a negotiation email."""
    score: int                                  # 0-100
    issues: list[Issue] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    rewritten_version: str = ""
    key_insight: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _locate_phrase(text: str, phrase: str) -> str:
    """Return a rough location descriptor for *phrase* inside *text*."""
    lower = text.lower()
    idx = lower.find(phrase.lower())
    if idx == -1:
        return "body"
    ratio = idx / max(len(text), 1)
    if ratio < 0.15:
        return "opening"
    if ratio > 0.80:
        return "closing"
    return "body"


def _word_count(text: str) -> int:
    return len(text.split())


def _find_hedging(text: str) -> list[Issue]:
    issues: list[Issue] = []
    lower = text.lower()
    for phrase in HEDGING_PHRASES:
        if phrase in lower:
            issues.append(Issue(
                severity=Severity.HIGH,
                location=_locate_phrase(text, phrase),
                issue_type="hedging",
                issue=f'Hedging language detected: "{phrase}"',
                suggestion=f'Remove "{phrase}" — state your request directly.',
            ))
    return issues


def _find_passive(text: str) -> list[Issue]:
    issues: list[Issue] = []
    for pattern in PASSIVE_PATTERNS:
        match = pattern.search(text)
        if match:
            matched = match.group()
            issues.append(Issue(
                severity=Severity.MEDIUM,
                location=_locate_phrase(text, matched),
                issue_type="passive_voice",
                issue=f'Passive construction: "{matched}"',
                suggestion="Rewrite in active voice with yourself as the subject.",
            ))
    return issues


def _check_anchor(text: str) -> list[Issue]:
    if MONEY_PATTERN.search(text):
        return []
    return [Issue(
        severity=Severity.HIGH,
        location="body",
        issue_type="missing_anchor",
        issue="No specific dollar amount mentioned.",
        suggestion=(
            "Include a concrete number — e.g. '$95,000'. "
            "Research shows the first number anchors the negotiation."
        ),
    )]


def _check_justification(text: str) -> list[Issue]:
    lower = text.lower()
    justification_signals = [
        "because", "based on", "given that", "considering",
        "my research shows", "market data", "comparable",
        "i've delivered", "i contributed", "track record",
        "benchmark", "industry standard",
    ]
    if any(signal in lower for signal in justification_signals):
        return []
    return [Issue(
        severity=Severity.HIGH,
        location="body",
        issue_type="missing_justification",
        issue="No justification provided for your ask.",
        suggestion=(
            "Add a reason: market data, your accomplishments, or "
            "comparable role salaries. 'Because' is the most persuasive word."
        ),
    )]


def _check_length(text: str) -> list[Issue]:
    wc = _word_count(text)
    if wc > 300:
        return [Issue(
            severity=Severity.MEDIUM,
            location="body",
            issue_type="too_long",
            issue=f"Email is {wc} words — over 300 loses impact.",
            suggestion="Trim to under 250 words. Cut backstory, keep data and the ask.",
        )]
    if wc < 30:
        return [Issue(
            severity=Severity.LOW,
            location="body",
            issue_type="too_short",
            issue=f"Email is only {wc} words — may lack substance.",
            suggestion="Add context: your value, market data, and a clear ask.",
        )]
    return []


def _check_emotional(text: str) -> list[Issue]:
    issues: list[Issue] = []
    lower = text.lower()
    for phrase in EMOTIONAL_TRIGGERS:
        if phrase in lower:
            issues.append(Issue(
                severity=Severity.MEDIUM,
                location=_locate_phrase(text, phrase),
                issue_type="emotional_language",
                issue=f'Emotionally charged language: "{phrase}"',
                suggestion="Replace with neutral, data-driven language.",
            ))
    return issues


def _check_gratitude_opening(text: str) -> list[Issue]:
    # Check the first ~100 characters
    opening = text[:min(150, len(text))].lower()
    if any(phrase in opening for phrase in GRATITUDE_OPENERS):
        return []
    return [Issue(
        severity=Severity.LOW,
        location="opening",
        issue_type="missing_gratitude",
        issue="No gratitude or enthusiasm in the opening.",
        suggestion=(
            'Start with appreciation — e.g. "Thank you for the offer — '
            'I\'m excited about the role."'
        ),
    )]


def _check_specific_close(text: str) -> list[Issue]:
    # Check the last ~200 characters
    closing = text[-min(250, len(text)):].lower()
    if any(phrase in closing for phrase in SPECIFIC_ASK_CLOSERS):
        return []
    return [Issue(
        severity=Severity.MEDIUM,
        location="closing",
        issue_type="missing_specific_close",
        issue="No specific ask or next-step in the closing.",
        suggestion=(
            'End with a clear action — e.g. "I\'d like to discuss a base '
            'salary of $X. Can we find 15 minutes this week?"'
        ),
    )]


def _detect_strengths(text: str) -> list[str]:
    strengths: list[str] = []
    lower = text.lower()

    power_count = sum(1 for p in POWER_PHRASES if p in lower)
    if power_count >= 2:
        strengths.append(f"Uses {power_count} power phrases — confident tone.")
    elif power_count == 1:
        strengths.append("Includes at least one power phrase.")

    if MONEY_PATTERN.search(text):
        strengths.append("Includes a specific dollar anchor.")

    wc = _word_count(text)
    if 100 <= wc <= 250:
        strengths.append(f"Good length ({wc} words) — concise and substantive.")

    opening = text[:min(150, len(text))].lower()
    if any(p in opening for p in GRATITUDE_OPENERS):
        strengths.append("Opens with gratitude — sets a collaborative tone.")

    return strengths


# ---------------------------------------------------------------------------
# Rewriter
# ---------------------------------------------------------------------------

def _rewrite(text: str, issues: list[Issue]) -> str:
    """
    Apply mechanical fixes for the most common issues.

    This is a best-effort pass — it removes hedging phrases and cleans up
    some passive constructions. It does NOT invent new content (no LLM).
    """
    rewritten = text

    # Remove hedging phrases
    for phrase in HEDGING_PHRASES:
        pattern = re.compile(re.escape(phrase) + r"[,\s]*", re.IGNORECASE)
        rewritten = pattern.sub("", rewritten)

    # Clean up double spaces / leading commas left by removals
    rewritten = re.sub(r"\s{2,}", " ", rewritten)
    rewritten = re.sub(r"\s*,\s*,", ",", rewritten)
    rewritten = re.sub(r"^\s*,\s*", "", rewritten, flags=re.MULTILINE)

    # Capitalize first letter of sentences that may have been lowered
    rewritten = re.sub(r"(?<=\.\s)([a-z])", lambda m: m.group(1).upper(), rewritten)
    rewritten = re.sub(r"^([a-z])", lambda m: m.group(1).upper(), rewritten)

    # Strip leading/trailing whitespace per line
    rewritten = "\n".join(line.strip() for line in rewritten.splitlines())

    return rewritten.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def audit_negotiation_email(email_text: str) -> EmailAudit:
    """
    Analyse a draft negotiation email and return structured feedback.

    All detection is regex/keyword-based — no LLM dependency.

    Parameters
    ----------
    email_text : str
        The full text of the draft email.

    Returns
    -------
    EmailAudit
        Score (0-100), categorised issues with suggestions, strengths,
        a mechanically rewritten version, and a headline insight.

    Examples
    --------
    >>> audit = audit_negotiation_email(
    ...     "Hi, I was hoping if possible to maybe get a raise. "
    ...     "Sorry to ask but I feel like I deserve more."
    ... )
    >>> audit.score < 50
    True
    >>> sum(1 for i in audit.issues if i.issue_type == "hedging") >= 3
    True

    >>> good = audit_negotiation_email(
    ...     "Thank you for the offer — I'm excited about the role. "
    ...     "Based on my research, comparable positions pay $95,000. "
    ...     "I've contributed $200K in revenue this year. "
    ...     "I'd like to discuss a base salary of $95,000. "
    ...     "Can we find 15 minutes this week?"
    ... )
    >>> good.score >= 80
    True
    >>> len(good.strengths) >= 2
    True
    """
    all_issues: list[Issue] = []

    all_issues.extend(_find_hedging(email_text))
    all_issues.extend(_find_passive(email_text))
    all_issues.extend(_check_anchor(email_text))
    all_issues.extend(_check_justification(email_text))
    all_issues.extend(_check_length(email_text))
    all_issues.extend(_check_emotional(email_text))
    all_issues.extend(_check_gratitude_opening(email_text))
    all_issues.extend(_check_specific_close(email_text))

    # Score: start at 100, deduct per issue (capped at 0)
    score = 100
    for issue in all_issues:
        score -= SEVERITY_DEDUCTIONS[issue.severity]
    score = max(0, score)

    # Bonus for power phrases (up to +10, cannot exceed 100)
    lower = email_text.lower()
    power_count = sum(1 for p in POWER_PHRASES if p in lower)
    score = min(100, score + min(power_count * 3, 10))

    strengths = _detect_strengths(email_text)
    rewritten = _rewrite(email_text, all_issues)

    issue_count = len(all_issues)
    high_count = sum(1 for i in all_issues if i.severity == Severity.HIGH)

    if issue_count == 0:
        key_insight = "Strong email — clear, confident, and well-structured."
    elif high_count >= 3:
        key_insight = (
            f"{high_count} critical issues found. The hedging and missing "
            f"specifics will cost you leverage — fix these before sending."
        )
    elif high_count >= 1:
        key_insight = (
            f"{issue_count} issue(s) found ({high_count} critical). "
            f"A few targeted edits will significantly strengthen your position."
        )
    else:
        key_insight = (
            f"{issue_count} minor issue(s). Solid foundation — "
            f"small tweaks will polish it."
        )

    return EmailAudit(
        score=score,
        issues=all_issues,
        strengths=strengths,
        rewritten_version=rewritten,
        key_insight=key_insight,
    )
