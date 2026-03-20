"""
API layer for offer analysis — thin wrapper around core.offer_analyzer.

Provides:
- analyze_offer(text) — parse free text and return an API-shaped OfferAnalysis
- get_market_data / get_available_roles / get_available_locations — benchmark lookups
- calculate_earnings_impact — lifetime earnings calculator
- audit_email — negotiation email draft scorer

All market data and analysis logic lives in core.offer_analyzer; this module
re-exports convenience types and adds API-specific features (earnings impact,
email audit) that the core does not include.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Re-use core benchmarks and helpers.
from dealsim_mvp.core.offer_analyzer import (
    SALARY_BENCHMARKS as _CORE_BENCHMARKS,
    LOCATION_MULTIPLIERS as _CORE_LOCATIONS,
    _normalize_key,
    _get_location_multiplier,
)


# ---------------------------------------------------------------------------
# Bundled market data — derived from core benchmarks, keyed by role+city for
# backward-compatible API access.  This is a *view* over core data, not a copy.
# ---------------------------------------------------------------------------

# Build per-city benchmarks from core role/level data * location multiplier.
# For the API layer we expose senior-level numbers per city to keep the old
# interface working.  Unknown cities fall back to the "default" (1.0) multiplier.
def _build_api_benchmarks() -> dict[str, dict[str, dict[str, float]]]:
    """Derive role -> city -> percentile dict from core data."""
    out: dict[str, dict[str, dict[str, float]]] = {}
    cities = [k for k in _CORE_LOCATIONS if k != "default"]
    for role, levels in _CORE_BENCHMARKS.items():
        senior = levels.get("senior", levels.get("mid", {}))
        city_map: dict[str, dict[str, float]] = {}
        for city in cities:
            mult = _CORE_LOCATIONS.get(city, 1.0)
            city_map[city] = {k: v * mult for k, v in senior.items()}
        # Also add a "national" key at 1.0 multiplier.
        city_map["national"] = {k: float(v) for k, v in senior.items()}
        out[role] = city_map
    return out


SALARY_BENCHMARKS = _build_api_benchmarks()

# Role aliases for fuzzy matching
_ROLE_ALIASES: dict[str, str] = {
    "swe": "software_engineer",
    "sde": "software_engineer",
    "developer": "software_engineer",
    "engineer": "software_engineer",
    "senior_engineer": "software_engineer",
    "senior_swe": "software_engineer",
    "staff_engineer": "software_engineer",
    "pm": "product_manager",
    "product": "product_manager",
    "ds": "data_scientist",
    "ml_engineer": "data_scientist",
    "ux_designer": "designer",
    "ui_designer": "designer",
    "marketing": "marketing_manager",
    "devops": "devops_sre",
    "sre": "devops_sre",
    "data_eng": "data_engineer",
    "eng_manager": "engineering_manager",
}

_LOCATION_ALIASES: dict[str, str] = {
    "sf": "san_francisco",
    "bay_area": "san_francisco",
    "silicon_valley": "san_francisco",
    "nyc": "new_york",
    "manhattan": "new_york",
    "sea": "seattle",
    "atx": "austin",
    "chi": "chicago",
    "remote": "remote",
    "us": "national",
    "usa": "national",
    "united_states": "national",
}


# ---------------------------------------------------------------------------
# Output types (kept for backward compatibility with existing API consumers)
# ---------------------------------------------------------------------------

@dataclass
class OfferComponent:
    """A parsed component of a job offer."""
    name: str
    value: str
    numeric_value: float | None = None
    negotiability: str = "medium"  # "high", "medium", "low", "fixed"
    market_position: str | None = None  # "below", "at", "above" market
    notes: str = ""


@dataclass
class CounterStrategy:
    """A suggested counter-offer strategy."""
    name: str
    description: str
    suggested_counter: str
    risk_level: str  # "low", "medium", "high"
    rationale: str


@dataclass
class OfferAnalysis:
    """Full analysis of a job offer."""
    components: list[OfferComponent]
    overall_market_position: str  # "below_market", "at_market", "above_market"
    overall_score: int  # 0-100
    counter_strategies: list[CounterStrategy]
    key_insights: list[str]


@dataclass
class MarketData:
    """Salary benchmark data for a role/location."""
    role: str
    location: str
    p25: float
    p50: float
    p75: float
    p90: float
    source: str = "DealSim bundled BLS/H1B approximations (2026-Q1)"


@dataclass
class EarningsImpact:
    """Lifetime earnings impact calculation."""
    current_offer: float
    negotiated_offer: float
    difference_annual: float
    difference_5yr: float
    difference_10yr: float
    difference_career: float  # 30 years with 3% annual raises
    compounding_note: str


@dataclass
class EmailAudit:
    """Analysis of a negotiation email draft."""
    overall_score: int  # 0-100
    tone: str
    strengths: list[str]
    issues: list[str]
    suggestions: list[str]
    rewrite_hints: list[str]


# ---------------------------------------------------------------------------
# Offer analysis — delegates parsing to a local helper, keeps API shape
# ---------------------------------------------------------------------------

_MONEY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{1,2})?)\s*(k|K)?")

_NEGOTIABILITY_MAP = {
    "base": "high",
    "salary": "high",
    "base_salary": "high",
    "signing_bonus": "high",
    "sign_on": "high",
    "equity": "high",
    "stock": "high",
    "rsu": "medium",
    "bonus": "medium",
    "annual_bonus": "medium",
    "target_bonus": "medium",
    "vacation": "medium",
    "pto": "medium",
    "remote": "medium",
    "title": "medium",
    "start_date": "low",
    "relocation": "low",
    "401k": "fixed",
    "health": "fixed",
    "insurance": "fixed",
}


def analyze_offer(offer_text: str) -> OfferAnalysis:
    """Parse and analyse an offer from free text."""
    components = _parse_offer_components(offer_text)
    strategies = _generate_counter_strategies(components)
    insights = _generate_insights(components)

    # Overall position
    base_comp = next((c for c in components if c.name in ("base_salary", "salary", "base")), None)
    if base_comp and base_comp.market_position:
        overall_pos = base_comp.market_position + "_market"
    else:
        overall_pos = "unknown"

    # Score: base on how many components are above/at/below market
    score = 50
    for c in components:
        if c.market_position == "above":
            score += 10
        elif c.market_position == "below":
            score -= 10
    score = max(0, min(100, score))

    return OfferAnalysis(
        components=components,
        overall_market_position=overall_pos,
        overall_score=score,
        counter_strategies=strategies,
        key_insights=insights,
    )


def get_market_data(role: str, location: str) -> MarketData | None:
    """Look up salary benchmarks for a role and location."""
    role_key = _normalize_role(role)
    loc_key = _normalize_location(location)

    role_data = SALARY_BENCHMARKS.get(role_key)
    if role_data is None:
        return None

    loc_data = role_data.get(loc_key)
    if loc_data is None:
        loc_data = role_data.get("national")
    if loc_data is None:
        return None

    return MarketData(
        role=role_key,
        location=loc_key,
        p25=loc_data["p25"],
        p50=loc_data["p50"],
        p75=loc_data["p75"],
        p90=loc_data["p90"],
    )


def get_available_roles() -> list[str]:
    """Return list of roles with benchmark data."""
    return list(SALARY_BENCHMARKS.keys())


def get_available_locations(role: str) -> list[str]:
    """Return locations with data for a given role."""
    role_key = _normalize_role(role)
    role_data = SALARY_BENCHMARKS.get(role_key, {})
    return list(role_data.keys())


def calculate_earnings_impact(current: float, negotiated: float) -> EarningsImpact:
    """Calculate the lifetime earnings impact of negotiating a higher salary."""
    diff = negotiated - current
    annual_raise = 0.03  # 3% annual raises

    # Compound over N years: sum of diff * (1.03)^i for i in 0..N-1
    def compound_sum(years: int) -> float:
        return sum(diff * (1 + annual_raise) ** i for i in range(years))

    return EarningsImpact(
        current_offer=current,
        negotiated_offer=negotiated,
        difference_annual=diff,
        difference_5yr=round(compound_sum(5), 2),
        difference_10yr=round(compound_sum(10), 2),
        difference_career=round(compound_sum(30), 2),
        compounding_note=(
            f"A ${diff:,.0f}/yr increase compounds to ${compound_sum(30):,.0f} over a 30-year career "
            f"(assuming 3% annual raises). This does not include investment returns on the saved difference."
        ),
    )


def audit_email(email_text: str) -> EmailAudit:
    """Analyse a negotiation email draft for tone, structure, and effectiveness."""
    lower = email_text.lower()
    strengths: list[str] = []
    issues: list[str] = []
    suggestions: list[str] = []
    rewrite_hints: list[str] = []
    score = 50

    # Check for key elements
    has_specific_number = bool(_MONEY_RE.search(email_text))
    has_rationale = any(w in lower for w in ("because", "based on", "research", "market", "data", "competitive"))
    has_enthusiasm = any(w in lower for w in ("excited", "thrilled", "looking forward", "passionate", "eager"))
    has_gratitude = any(w in lower for w in ("thank", "grateful", "appreciate"))
    has_alternatives = any(w in lower for w in ("other offer", "alternative", "another opportunity", "competing"))
    has_apology = any(w in lower for w in ("sorry", "apologize", "i hate to", "i feel bad"))
    has_hedge = any(w in lower for w in ("just", "maybe", "i think maybe", "if possible", "if you could"))
    has_ultimatum = any(w in lower for w in ("or else", "final offer", "take it or leave", "non-negotiable"))

    # Tone assessment
    if has_apology and has_hedge:
        tone = "apologetic — undermines your position"
    elif has_ultimatum:
        tone = "aggressive — risks damaging the relationship"
    elif has_enthusiasm and has_gratitude and has_specific_number:
        tone = "professional and confident — excellent"
    elif has_enthusiasm and has_gratitude:
        tone = "warm but vague — needs a specific ask"
    else:
        tone = "neutral — functional but could be more engaging"

    # Score adjustments
    if has_specific_number:
        score += 15
        strengths.append("States a specific number — clear and direct.")
    else:
        score -= 10
        issues.append("No specific number mentioned — the email lacks a clear ask.")
        suggestions.append("Always include your specific target number. Vague asks get vague responses.")

    if has_rationale:
        score += 10
        strengths.append("Provides market-based rationale for the ask.")
    else:
        issues.append("No data or rationale backing the request.")
        suggestions.append("Reference market data, your experience, or competing offers to justify your number.")

    if has_enthusiasm:
        score += 5
        strengths.append("Expresses genuine enthusiasm for the role.")

    if has_gratitude:
        score += 5
        strengths.append("Shows gratitude — maintains relationship warmth.")
    else:
        suggestions.append("Open with gratitude for the offer before negotiating.")

    if has_alternatives:
        score += 10
        strengths.append("References alternatives — signals leverage.")

    if has_apology:
        score -= 15
        issues.append("Apologetic language weakens your position.")
        rewrite_hints.append("Remove 'sorry' and 'I feel bad' — negotiating is expected and professional.")

    if has_hedge:
        score -= 10
        issues.append("Hedge words ('just', 'maybe', 'if possible') signal uncertainty.")
        rewrite_hints.append("Replace 'I was just wondering if maybe...' with 'I'd like to discuss...'")

    if has_ultimatum:
        score -= 10
        issues.append("Ultimatum language can backfire. Frame as preference, not demand.")
        rewrite_hints.append("Replace 'This is my final number' with 'Based on my research, I believe X is fair.'")

    # Length check
    word_count = len(email_text.split())
    if word_count > 300:
        issues.append(f"Email is {word_count} words — aim for under 200 for clarity.")
        suggestions.append("Shorten to 3-4 paragraphs: gratitude, ask with rationale, enthusiasm, close.")
    elif word_count < 50:
        issues.append("Email is very short — may come across as dismissive.")
        suggestions.append("Add context: why you want the role, why the number is justified.")

    score = max(0, min(100, score))

    return EmailAudit(
        overall_score=score,
        tone=tone,
        strengths=strengths,
        issues=issues,
        suggestions=suggestions,
        rewrite_hints=rewrite_hints,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_role(role: str) -> str:
    key = role.lower().strip().replace(" ", "_").replace("-", "_")
    return _ROLE_ALIASES.get(key, key)


def _normalize_location(location: str) -> str:
    key = location.lower().strip().replace(" ", "_").replace("-", "_")
    return _LOCATION_ALIASES.get(key, key)


def _parse_offer_components(text: str) -> list[OfferComponent]:
    """Extract offer components from free text.

    Fixed: handles combined bonus formats (e.g. '15% annual bonus' +
    '$10k signing bonus') without regex group collisions.
    """
    components: list[OfferComponent] = []
    lower = text.lower()

    # Try to extract base salary
    base_patterns = [
        (r"base\s*(?:salary)?\s*(?:of|:)?\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*(k|K)?", "base_salary"),
        (r"salary\s*(?:of|:)?\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*(k|K)?", "base_salary"),
        (r"\$\s*([\d,]+(?:\.\d{1,2})?)\s*(k|K)?\s*(?:base|salary|annual|per year|/yr)", "base_salary"),
    ]
    for pattern, name in base_patterns:
        m = re.search(pattern, lower)
        if m:
            val = float(m.group(1).replace(",", ""))
            if m.group(2) and m.group(2).lower() == "k":
                val *= 1000
            components.append(OfferComponent(
                name=name,
                value=f"${val:,.0f}",
                numeric_value=val,
                negotiability=_NEGOTIABILITY_MAP.get(name, "medium"),
            ))
            break

    # Signing bonus — match both "signing bonus of $X" and "$Xk signing bonus".
    sign_m = re.search(
        r"(?:sign(?:ing|[-\s]*on)\s+bonus\s*(?:of|:)?\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*(k|K)?|\$?\s*([\d,]+(?:\.\d{1,2})?)\s*(k|K)?\s*sign(?:ing|[-\s]*on)\s+bonus)",
        lower,
    )
    if sign_m:
        # Groups 1,2 = "signing bonus $X" pattern; groups 3,4 = "$X signing bonus" pattern.
        raw_val = sign_m.group(1) or sign_m.group(3)
        raw_k = sign_m.group(2) or sign_m.group(4)
        val = float(raw_val.replace(",", ""))
        if raw_k and raw_k.lower() == "k":
            val *= 1000
        components.append(OfferComponent(
            name="signing_bonus",
            value=f"${val:,.0f}",
            numeric_value=val,
            negotiability="high",
        ))

    # Equity/RSU
    eq_m = re.search(r"(?:equity|rsu|stock|shares?)\s*(?:of|:)?\s*\$?\s*([\d,]+(?:\.\d{1,2})?)\s*(k|K)?", lower)
    if eq_m:
        val = float(eq_m.group(1).replace(",", ""))
        if eq_m.group(2) and eq_m.group(2).lower() == "k":
            val *= 1000
        components.append(OfferComponent(
            name="equity",
            value=f"${val:,.0f}",
            numeric_value=val,
            negotiability="high",
        ))

    # Annual/target bonus (percentage) — only look for *non-signing* bonus lines.
    # Match "X% annual bonus" or "X% bonus" but NOT inside "signing bonus" context.
    bonus_pct_m = re.search(r"(\d+)%\s*(?:annual\s+)?bonus", lower)
    if bonus_pct_m:
        # Make sure this match is not inside a "signing bonus" phrase.
        start = bonus_pct_m.start()
        preceding = lower[max(0, start - 20):start]
        if "sign" not in preceding:
            components.append(OfferComponent(
                name="annual_bonus",
                value=f"{bonus_pct_m.group(1)}% target",
                negotiability="medium",
            ))

    # Dollar-amount annual bonus (not signing).
    if not bonus_pct_m or "sign" in lower[max(0, bonus_pct_m.start() - 20):bonus_pct_m.start()]:
        bonus_dollar_m = re.search(
            r"(?:annual\s+)?bonus\s*(?:of|:)?\s*\$\s*([\d,]+(?:\.\d{1,2})?)\s*(k|K)?",
            lower,
        )
        if bonus_dollar_m and not sign_m:
            val = float(bonus_dollar_m.group(1).replace(",", ""))
            if bonus_dollar_m.group(2) and bonus_dollar_m.group(2).lower() == "k":
                val *= 1000
            components.append(OfferComponent(
                name="annual_bonus",
                value=f"${val:,.0f}",
                numeric_value=val,
                negotiability="medium",
            ))

    # PTO/vacation
    pto_m = re.search(r"(\d+)\s*(?:days?|weeks?)\s*(?:of\s*)?(?:pto|vacation|paid\s*time\s*off)", lower)
    if pto_m:
        components.append(OfferComponent(
            name="pto",
            value=f"{pto_m.group(1)} days",
            negotiability="medium",
        ))

    # Remote
    if any(w in lower for w in ("remote", "hybrid", "work from home", "wfh")):
        remote_type = "remote" if "remote" in lower else "hybrid"
        components.append(OfferComponent(
            name="remote",
            value=remote_type,
            negotiability="medium",
        ))

    # If no components found, try to extract any number as base salary
    if not components:
        m = _MONEY_RE.search(text)
        if m:
            val = float(m.group(1).replace(",", ""))
            if m.group(2) and m.group(2).lower() == "k":
                val *= 1000
            components.append(OfferComponent(
                name="base_salary",
                value=f"${val:,.0f}",
                numeric_value=val,
                negotiability="high",
            ))

    return components


def _generate_counter_strategies(components: list[OfferComponent]) -> list[CounterStrategy]:
    """Generate counter-offer strategies based on parsed offer components."""
    strategies: list[CounterStrategy] = []

    base = next((c for c in components if c.name == "base_salary" and c.numeric_value), None)
    has_signing = any(c.name == "signing_bonus" for c in components)
    has_equity = any(c.name == "equity" for c in components)

    if base and base.numeric_value:
        target_10 = base.numeric_value * 1.10
        target_15 = base.numeric_value * 1.15

        strategies.append(CounterStrategy(
            name="Standard counter (+10-15%)",
            description=f"Counter at ${target_10:,.0f}-${target_15:,.0f} with market data justification.",
            suggested_counter=f"${target_15:,.0f}",
            risk_level="low",
            rationale="A 10-15% counter is standard and expected. Most employers have budget headroom.",
        ))

        if not has_signing:
            sign_val = base.numeric_value * 0.10
            strategies.append(CounterStrategy(
                name="Add signing bonus",
                description=f"Accept base near current, request ${sign_val:,.0f} signing bonus.",
                suggested_counter=f"Base: ${base.numeric_value:,.0f} + ${sign_val:,.0f} signing",
                risk_level="low",
                rationale="Signing bonuses come from a different budget line. Easy for employers to approve.",
            ))

        if not has_equity:
            strategies.append(CounterStrategy(
                name="Request equity component",
                description="Ask for RSUs or stock options as part of total compensation.",
                suggested_counter="Request equity discussion",
                risk_level="medium",
                rationale="Equity aligns your incentives with the company. Especially valuable at growth-stage companies.",
            ))

        strategies.append(CounterStrategy(
            name="Package optimization",
            description="Accept base, negotiate PTO, remote days, title, or start date.",
            suggested_counter="Base as offered + improved package terms",
            risk_level="low",
            rationale="Non-salary items often cost the employer little but have high value to you.",
        ))

    return strategies


def _generate_insights(components: list[OfferComponent]) -> list[str]:
    """Generate key insights about the offer."""
    insights: list[str] = []

    base = next((c for c in components if c.name == "base_salary" and c.numeric_value), None)
    if base and base.numeric_value:
        insights.append(f"Base salary of {base.value} is the primary negotiation lever.")
        if base.numeric_value < 50000:
            insights.append("This appears to be an hourly rate or part-time role — verify the pay structure.")

    high_neg = [c for c in components if c.negotiability == "high"]
    if high_neg:
        names = ", ".join(c.name.replace("_", " ") for c in high_neg)
        insights.append(f"Highest negotiability: {names}.")

    if not any(c.name in ("equity", "rsu", "stock") for c in components):
        insights.append("No equity mentioned — this is a common negotiation lever to add.")

    if not any(c.name == "signing_bonus" for c in components):
        insights.append("No signing bonus in the offer — often the easiest component to add.")

    return insights
