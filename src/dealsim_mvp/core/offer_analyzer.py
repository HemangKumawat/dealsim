"""
Job-offer analyzer: market positioning, negotiability scoring, and counter-offer strategy.

Turns a raw job offer into actionable negotiation intelligence by comparing each
compensation component against bundled market benchmarks, identifying missing
elements, and generating three counter-offer strategies at different risk levels.

Data sources:
    All salary benchmarks are static and bundled (no external API calls).
    Ranges approximate US-market 2026 data for tech-adjacent roles
    (2024 base data adjusted +8% for 2025-2026 wage growth).

Unit convention:
    All monetary values are USD annual unless noted otherwise.
    Equity values are total-grant values (not per-year).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Data vintage — bump this when refreshing benchmarks.
# ---------------------------------------------------------------------------
DATA_VINTAGE = "2026-Q1 (2024 base +8%)"

# ---------------------------------------------------------------------------
# Bounds for salary validation.
# ---------------------------------------------------------------------------
SALARY_MIN = 1          # Reject 0 and negative
SALARY_MAX = 10_000_000


# ---------------------------------------------------------------------------
# Static market data (2024 values * 1.08 for 2026 adjustment)
# ---------------------------------------------------------------------------

SALARY_BENCHMARKS: dict[str, dict[str, dict[str, int]]] = {
    "software_engineer": {
        "junior":  {"p25": 86_400,  "p50": 102_600, "p75": 124_200, "p90": 140_400},
        "mid":     {"p25": 108_000, "p50": 129_600, "p75": 156_600, "p90": 178_200},
        "senior":  {"p25": 140_400, "p50": 167_400, "p75": 199_800, "p90": 226_800},
        "staff":   {"p25": 183_600, "p50": 216_000, "p75": 259_200, "p90": 302_400},
        "lead":    {"p25": 167_400, "p50": 194_400, "p75": 232_200, "p90": 270_000},
    },
    "product_manager": {
        "junior":  {"p25": 81_000,  "p50": 97_200,  "p75": 118_800, "p90": 135_000},
        "mid":     {"p25": 113_400, "p50": 135_000, "p75": 162_000, "p90": 183_600},
        "senior":  {"p25": 145_800, "p50": 172_800, "p75": 205_200, "p90": 237_600},
        "staff":   {"p25": 189_000, "p50": 226_800, "p75": 270_000, "p90": 313_200},
        "lead":    {"p25": 162_000, "p50": 189_000, "p75": 226_800, "p90": 264_600},
    },
    "data_scientist": {
        "junior":  {"p25": 84_240,  "p50": 100_440, "p75": 120_960, "p90": 138_240},
        "mid":     {"p25": 113_400, "p50": 135_000, "p75": 162_000, "p90": 185_760},
        "senior":  {"p25": 145_800, "p50": 172_800, "p75": 207_360, "p90": 237_600},
        "staff":   {"p25": 183_600, "p50": 221_400, "p75": 264_600, "p90": 307_800},
        "lead":    {"p25": 167_400, "p50": 199_800, "p75": 237_600, "p90": 280_800},
    },
    "data_engineer": {
        "junior":  {"p25": 82_080,  "p50": 99_360,  "p75": 118_800, "p90": 136_080},
        "mid":     {"p25": 111_240, "p50": 132_840, "p75": 159_840, "p90": 183_600},
        "senior":  {"p25": 143_640, "p50": 172_800, "p75": 205_200, "p90": 237_600},
        "staff":   {"p25": 178_200, "p50": 216_000, "p75": 259_200, "p90": 302_400},
        "lead":    {"p25": 162_000, "p50": 194_400, "p75": 232_200, "p90": 270_000},
    },
    "devops_sre": {
        "junior":  {"p25": 84_240,  "p50": 100_440, "p75": 120_960, "p90": 138_240},
        "mid":     {"p25": 111_240, "p50": 132_840, "p75": 159_840, "p90": 183_600},
        "senior":  {"p25": 140_400, "p50": 170_640, "p75": 203_040, "p90": 232_200},
        "staff":   {"p25": 178_200, "p50": 216_000, "p75": 259_200, "p90": 302_400},
        "lead":    {"p25": 162_000, "p50": 194_400, "p75": 232_200, "p90": 270_000},
    },
    "engineering_manager": {
        "junior":  {"p25": 118_800, "p50": 140_400, "p75": 167_400, "p90": 189_000},
        "mid":     {"p25": 145_800, "p50": 172_800, "p75": 205_200, "p90": 237_600},
        "senior":  {"p25": 172_800, "p50": 205_200, "p75": 243_000, "p90": 280_800},
        "staff":   {"p25": 205_200, "p50": 243_000, "p75": 291_600, "p90": 340_200},
        "lead":    {"p25": 194_400, "p50": 232_200, "p75": 275_400, "p90": 324_000},
    },
    "designer": {
        "junior":  {"p25": 64_800,  "p50": 77_760,  "p75": 95_040,  "p90": 108_000},
        "mid":     {"p25": 91_800,  "p50": 110_160, "p75": 131_760, "p90": 151_200},
        "senior":  {"p25": 124_200, "p50": 149_040, "p75": 178_200, "p90": 205_200},
        "staff":   {"p25": 162_000, "p50": 192_240, "p75": 226_800, "p90": 264_600},
        "lead":    {"p25": 145_800, "p50": 172_800, "p75": 207_360, "p90": 243_000},
    },
    "marketing_manager": {
        "junior":  {"p25": 56_160,  "p50": 66_960,  "p75": 81_000,  "p90": 95_040},
        "mid":     {"p25": 77_760,  "p50": 95_040,  "p75": 116_640, "p90": 135_000},
        "senior":  {"p25": 108_000, "p50": 129_600, "p75": 159_840, "p90": 185_760},
        "staff":   {"p25": 140_400, "p50": 167_400, "p75": 203_040, "p90": 237_600},
        "lead":    {"p25": 127_440, "p50": 151_200, "p75": 183_600, "p90": 216_000},
    },
    "sales_representative": {
        "junior":  {"p25": 48_600,  "p50": 59_400,  "p75": 73_440,  "p90": 86_400},
        "mid":     {"p25": 70_200,  "p50": 86_400,  "p75": 108_000, "p90": 127_440},
        "senior":  {"p25": 97_200,  "p50": 118_800, "p75": 149_040, "p90": 175_000},
        "staff":   {"p25": 129_600, "p50": 156_600, "p75": 192_240, "p90": 226_800},
        "lead":    {"p25": 116_640, "p50": 140_400, "p75": 172_800, "p90": 205_200},
    },
    "general": {
        "junior":  {"p25": 59_400,  "p50": 70_200,  "p75": 86_400,  "p90": 102_600},
        "mid":     {"p25": 81_000,  "p50": 99_360,  "p75": 120_960, "p90": 140_400},
        "senior":  {"p25": 108_000, "p50": 135_000, "p75": 167_400, "p90": 194_400},
        "staff":   {"p25": 151_200, "p50": 183_600, "p75": 221_400, "p90": 259_200},
        "lead":    {"p25": 135_000, "p50": 164_160, "p75": 199_800, "p90": 235_440},
    },
}

LOCATION_MULTIPLIERS: dict[str, float] = {
    "san_francisco": 1.30,
    "sf":            1.30,
    "bay_area":      1.30,
    "new_york":      1.25,
    "nyc":           1.25,
    "new_york_city": 1.25,
    "seattle":       1.15,
    "boston":         1.15,
    "los_angeles":   1.12,
    "la":            1.12,
    "washington_dc": 1.10,
    "dc":            1.10,
    "san_diego":     1.08,
    "portland":      1.05,
    "miami":         1.08,
    "philadelphia":  1.02,
    "pittsburgh":    0.94,
    "raleigh":       0.98,
    "austin":        1.00,
    "denver":        1.00,
    "chicago":       0.95,
    "atlanta":       0.95,
    "dallas":        0.92,
    "houston":       0.92,
    "phoenix":       0.90,
    "minneapolis":   0.92,
    "remote":        1.00,
    "default":       1.00,
}

# Equity benchmarks as fraction of base salary (4-year total grant).
EQUITY_BENCHMARKS: dict[str, dict[str, dict[str, float]]] = {
    "software_engineer": {
        "junior": {"p25": 0.2, "p50": 0.5, "p75": 1.0, "p90": 1.5},
        "mid":    {"p25": 0.3, "p50": 0.8, "p75": 1.5, "p90": 2.5},
        "senior": {"p25": 0.5, "p50": 1.2, "p75": 2.5, "p90": 4.0},
        "staff":  {"p25": 1.0, "p50": 2.0, "p75": 4.0, "p90": 6.0},
        "lead":   {"p25": 0.8, "p50": 1.5, "p75": 3.0, "p90": 5.0},
    },
    "general": {
        "junior": {"p25": 0.0, "p50": 0.2, "p75": 0.5, "p90": 1.0},
        "mid":    {"p25": 0.1, "p50": 0.4, "p75": 1.0, "p90": 1.8},
        "senior": {"p25": 0.3, "p50": 0.8, "p75": 1.8, "p90": 3.0},
        "staff":  {"p25": 0.5, "p50": 1.5, "p75": 3.0, "p90": 5.0},
        "lead":   {"p25": 0.4, "p50": 1.2, "p75": 2.5, "p90": 4.0},
    },
}

# Signing bonus benchmarks (absolute $, not ratio) — 2026-adjusted.
SIGNING_BONUS_BENCHMARKS: dict[str, dict[str, int]] = {
    "junior": {"p25": 5_400,  "p50": 10_800, "p75": 21_600, "p90": 32_400},
    "mid":    {"p25": 10_800, "p50": 21_600, "p75": 37_800, "p90": 54_000},
    "senior": {"p25": 16_200, "p50": 32_400, "p75": 54_000, "p90": 81_000},
    "staff":  {"p25": 27_000, "p50": 54_000, "p75": 86_400, "p90": 108_000},
    "lead":   {"p25": 21_600, "p50": 43_200, "p75": 70_200, "p90": 97_200},
}


class Negotiability(str, Enum):
    """How likely a component is to move during negotiation."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class ComponentNegotiability:
    negotiability: Negotiability
    typical_move: str          # e.g. "5-15%" or "$10K-$50K"
    note: str


COMPONENT_NEGOTIABILITY: dict[str, ComponentNegotiability] = {
    "base_salary": ComponentNegotiability(
        Negotiability.HIGH, "5-15%",
        "Strongest lever; anchor high with market data.",
    ),
    "signing_bonus": ComponentNegotiability(
        Negotiability.HIGH, "$10K-$50K",
        "Easy budget line for the employer to flex on.",
    ),
    "equity": ComponentNegotiability(
        Negotiability.MEDIUM, "10-30%",
        "Requires comp-committee approval at many companies.",
    ),
    "annual_bonus": ComponentNegotiability(
        Negotiability.LOW, "0-5% target increase",
        "Usually formula-based; target % is rarely changed.",
    ),
    "remote_days": ComponentNegotiability(
        Negotiability.MEDIUM, "1-3 extra days/week",
        "Increasingly flexible post-2020; low cost to employer.",
    ),
    "start_date": ComponentNegotiability(
        Negotiability.HIGH, "2-8 weeks",
        "Often used as leverage: offer to start sooner in exchange for higher comp.",
    ),
    "title": ComponentNegotiability(
        Negotiability.MEDIUM, "one level",
        "Costs the employer nothing; high career-compound value.",
    ),
    "review_cycle": ComponentNegotiability(
        Negotiability.HIGH, "6-month accelerated review",
        "Ask for a 6-month performance + comp review instead of 12-month.",
    ),
    "relocation": ComponentNegotiability(
        Negotiability.MEDIUM, "$5K-$20K",
        "Lump-sum relocation is easier to negotiate than managed relo.",
    ),
    "pto_days": ComponentNegotiability(
        Negotiability.LOW, "0-5 extra days",
        "Hard to change at companies with uniform PTO policies.",
    ),
}

# Standard offer components to check for "missing elements" analysis.
STANDARD_COMPONENTS: list[str] = [
    "base_salary",
    "signing_bonus",
    "equity",
    "annual_bonus",
    "remote_days",
    "start_date",
    "title",
    "review_cycle",
    "relocation",
    "pto_days",
]


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class PercentilePosition:
    """Where a single compensation component sits relative to market."""
    component: str
    value: float
    percentile: int         # 0-100
    market_p50: float       # median benchmark (location-adjusted)
    delta_vs_median: float  # value - market_p50 (positive = above median)


@dataclass
class MissingComponent:
    """A compensation element that comparable offers typically include."""
    component: str
    typical_value: str      # human-readable range
    negotiability: Negotiability
    note: str


@dataclass
class CounterStrategy:
    """One counter-offer strategy at a given aggressiveness level."""
    name: str                           # "conservative" | "balanced" | "aggressive"
    description: str
    adjustments: dict[str, str]         # component -> suggested ask (human-readable)
    estimated_upside: float             # additional $ relative to current offer
    risk_note: str


@dataclass
class OfferAnalysis:
    """Complete analysis of a job offer."""
    role: str
    level: str
    location: str
    location_multiplier: float

    percentile_positions: list[PercentilePosition]
    missing_components: list[MissingComponent]
    negotiability_scores: dict[str, Negotiability]
    counter_strategies: list[CounterStrategy]
    total_potential_upside: float       # $ from balanced strategy
    market_comparison: str              # one-paragraph summary


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_key(raw: str) -> str:
    """Lowercase, strip whitespace, replace spaces/hyphens with underscores."""
    return re.sub(r"[\s\-]+", "_", raw.strip().lower())


def _get_benchmarks(role: str, level: str) -> dict[str, int]:
    """Return salary percentile dict for a role+level, falling back to 'general'."""
    role_key = _normalize_key(role)
    level_key = _normalize_key(level)
    role_data = SALARY_BENCHMARKS.get(role_key, SALARY_BENCHMARKS["general"])
    return role_data.get(level_key, role_data.get("mid", SALARY_BENCHMARKS["general"]["mid"]))


def _get_equity_benchmarks(role: str, level: str) -> dict[str, float]:
    """Return equity-ratio percentile dict, falling back to 'general'."""
    role_key = _normalize_key(role)
    level_key = _normalize_key(level)
    role_data = EQUITY_BENCHMARKS.get(role_key, EQUITY_BENCHMARKS["general"])
    return role_data.get(level_key, role_data.get("mid", EQUITY_BENCHMARKS["general"]["mid"]))


def _get_location_multiplier(location: str) -> float:
    loc_key = _normalize_key(location)
    return LOCATION_MULTIPLIERS.get(loc_key, LOCATION_MULTIPLIERS["default"])


def _estimate_percentile(value: float, benchmarks: dict[str, int | float]) -> int:
    """
    Estimate a percentile (0-100) by linear interpolation between benchmark points.

    Benchmark keys must include 'p25', 'p50', 'p75', 'p90'.
    Values below p25 extrapolate down to 0; values above p90 extrapolate up to 100.
    """
    points = [
        (0,   benchmarks["p25"] * 0.70),   # synthetic p0 anchor
        (25,  benchmarks["p25"]),
        (50,  benchmarks["p50"]),
        (75,  benchmarks["p75"]),
        (100, benchmarks["p90"] * 1.15),    # synthetic p100 anchor
    ]
    if value <= points[0][1]:
        return 0
    if value >= points[-1][1]:
        return 100
    for i in range(len(points) - 1):
        pctl_lo, val_lo = points[i]
        pctl_hi, val_hi = points[i + 1]
        if val_lo <= value <= val_hi:
            fraction = (value - val_lo) / (val_hi - val_lo) if val_hi != val_lo else 0.0
            return int(pctl_lo + fraction * (pctl_hi - pctl_lo))
    return 50  # fallback


def _format_currency(amount: float) -> str:
    """Format a dollar amount with commas and no decimals."""
    if amount >= 0:
        return f"${amount:,.0f}"
    return f"-${abs(amount):,.0f}"


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze_offer(
    role: str,
    level: str,
    location: str,
    base_salary: float,
    equity: float | None = None,
    signing_bonus: float | None = None,
    bonus_pct: float | None = None,
    other_components: dict[str, Any] | None = None,
) -> OfferAnalysis:
    """
    Analyze a job offer against market benchmarks.

    Parameters
    ----------
    role : str
        Job role (e.g. "software_engineer", "product_manager", "data_scientist").
        Unrecognized roles fall back to "general" benchmarks.
    level : str
        Seniority level ("junior", "mid", "senior", "staff", "lead").
    location : str
        City or "remote". Used to apply cost-of-living adjustment.
    base_salary : float
        Annual base salary in USD.
    equity : float, optional
        Total equity grant value in USD (4-year vest).
    signing_bonus : float, optional
        One-time signing bonus in USD.
    bonus_pct : float, optional
        Target annual bonus as a percentage (e.g. 15 means 15%).
    other_components : dict, optional
        Additional offer elements (e.g. {"remote_days": 3, "pto_days": 25}).

    Returns
    -------
    OfferAnalysis
        Complete market positioning, negotiability map, missing-element list,
        three counter-offer strategies, and estimated upside.

    Raises
    ------
    ValueError
        If base_salary is negative or exceeds $10M.
    """
    # --- Bounds checking ---
    if base_salary < SALARY_MIN:
        raise ValueError(
            f"base_salary must be > $0; got ${base_salary:,.0f}. "
            "Zero and negative salaries are not valid."
        )
    if base_salary > SALARY_MAX:
        raise ValueError(
            f"base_salary must be <= ${SALARY_MAX:,.0f}; got ${base_salary:,.0f}. "
            "If this is correct, contact support."
        )

    other = other_components or {}
    loc_mult = _get_location_multiplier(location)
    salary_bench = _get_benchmarks(role, level)
    equity_bench = _get_equity_benchmarks(role, level)
    level_key = _normalize_key(level)
    sign_bench = SIGNING_BONUS_BENCHMARKS.get(level_key, SIGNING_BONUS_BENCHMARKS["mid"])

    # Apply location multiplier to salary benchmarks.
    adj_salary_bench = {k: int(v * loc_mult) for k, v in salary_bench.items()}
    adj_sign_bench = {k: int(v * loc_mult) for k, v in sign_bench.items()}

    # --- Percentile positions ---
    positions: list[PercentilePosition] = []

    base_pctl = _estimate_percentile(base_salary, adj_salary_bench)
    positions.append(PercentilePosition(
        component="base_salary",
        value=base_salary,
        percentile=base_pctl,
        market_p50=float(adj_salary_bench["p50"]),
        delta_vs_median=base_salary - adj_salary_bench["p50"],
    ))

    if equity is not None:
        # Convert equity ratio benchmarks to absolute $ using the offer's base.
        abs_equity_bench = {k: v * adj_salary_bench["p50"] for k, v in equity_bench.items()}
        eq_pctl = _estimate_percentile(equity, abs_equity_bench)
        positions.append(PercentilePosition(
            component="equity",
            value=equity,
            percentile=eq_pctl,
            market_p50=abs_equity_bench["p50"],
            delta_vs_median=equity - abs_equity_bench["p50"],
        ))

    if signing_bonus is not None:
        sb_pctl = _estimate_percentile(signing_bonus, adj_sign_bench)
        positions.append(PercentilePosition(
            component="signing_bonus",
            value=signing_bonus,
            percentile=sb_pctl,
            market_p50=float(adj_sign_bench["p50"]),
            delta_vs_median=signing_bonus - adj_sign_bench["p50"],
        ))

    if bonus_pct is not None:
        # Simple heuristic: 10% target is median for most tech roles.
        bonus_bench = {"p25": 5, "p50": 10, "p75": 15, "p90": 25}
        bp_pctl = _estimate_percentile(bonus_pct, bonus_bench)
        annual_bonus_dollars = base_salary * bonus_pct / 100
        positions.append(PercentilePosition(
            component="annual_bonus",
            value=bonus_pct,
            percentile=bp_pctl,
            market_p50=10.0,
            delta_vs_median=bonus_pct - 10.0,
        ))

    # --- Missing components ---
    provided_keys: set[str] = {"base_salary"}
    if equity is not None:
        provided_keys.add("equity")
    if signing_bonus is not None:
        provided_keys.add("signing_bonus")
    if bonus_pct is not None:
        provided_keys.add("annual_bonus")
    for key in other:
        provided_keys.add(_normalize_key(key))

    missing: list[MissingComponent] = []
    for comp in STANDARD_COMPONENTS:
        if comp not in provided_keys:
            neg_info = COMPONENT_NEGOTIABILITY.get(comp)
            if neg_info is None:
                continue
            typical = neg_info.typical_move
            missing.append(MissingComponent(
                component=comp,
                typical_value=typical,
                negotiability=neg_info.negotiability,
                note=neg_info.note,
            ))

    # --- Negotiability scores ---
    negotiability_scores: dict[str, Negotiability] = {}
    for comp in provided_keys:
        neg_info = COMPONENT_NEGOTIABILITY.get(comp)
        if neg_info is not None:
            negotiability_scores[comp] = neg_info.negotiability

    # --- Counter-offer strategies ---
    strategies = _build_counter_strategies(
        base_salary=base_salary,
        equity=equity,
        signing_bonus=signing_bonus,
        bonus_pct=bonus_pct,
        adj_salary_bench=adj_salary_bench,
        adj_sign_bench=adj_sign_bench,
        equity_bench=equity_bench,
        loc_mult=loc_mult,
        missing=missing,
    )

    # Total potential upside = balanced strategy's estimated gain.
    balanced = next((s for s in strategies if s.name == "balanced"), strategies[1])
    total_upside = balanced.estimated_upside

    # --- Market comparison summary ---
    base_pos = positions[0]
    direction = "above" if base_pos.delta_vs_median >= 0 else "below"
    market_comparison = (
        f"Your base salary of {_format_currency(base_salary)} sits at the "
        f"{_ordinal(base_pos.percentile)} percentile for a {level} {role.replace('_', ' ')} "
        f"in {location} ({_format_currency(abs(base_pos.delta_vs_median))} {direction} "
        f"the market median of {_format_currency(base_pos.market_p50)}). "
    )
    if equity is not None and len(positions) > 1:
        eq_pos = next(p for p in positions if p.component == "equity")
        market_comparison += (
            f"Your equity grant of {_format_currency(equity)} is at the "
            f"{_ordinal(eq_pos.percentile)} percentile. "
        )
    if missing:
        names = ", ".join(m.component.replace("_", " ") for m in missing[:3])
        market_comparison += (
            f"This offer is missing {len(missing)} standard component(s) "
            f"({names}), which creates additional negotiation leverage."
        )

    return OfferAnalysis(
        role=_normalize_key(role),
        level=_normalize_key(level),
        location=_normalize_key(location),
        location_multiplier=loc_mult,
        percentile_positions=positions,
        missing_components=missing,
        negotiability_scores=negotiability_scores,
        counter_strategies=strategies,
        total_potential_upside=total_upside,
        market_comparison=market_comparison,
    )


def _ordinal(n: int) -> str:
    """Return '42nd', '71st', etc."""
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd','th','th','th','th','th','th'][n % 10]}"


def _build_counter_strategies(
    *,
    base_salary: float,
    equity: float | None,
    signing_bonus: float | None,
    bonus_pct: float | None,
    adj_salary_bench: dict[str, int],
    adj_sign_bench: dict[str, int],
    equity_bench: dict[str, float],
    loc_mult: float,
    missing: list[MissingComponent],
) -> list[CounterStrategy]:
    """
    Generate conservative, balanced, and aggressive counter-offer strategies.

    Each strategy targets a different percentile band:
      - Conservative: aim for p50-p60 on weak components.
      - Balanced: aim for p65-p75 across the board.
      - Aggressive: aim for p80-p90, push on every lever.
    """
    strategies: list[CounterStrategy] = []

    # Target percentile values for each strategy tier.
    tiers: list[tuple[str, str, str, str, float]] = [
        # (name, description, salary_target_key, risk_note, signing_floor_mult)
        (
            "conservative",
            "Low-risk: nudge underpaying components toward the median while "
            "preserving goodwill. Best when you have limited leverage or want "
            "to keep the relationship warm.",
            "p50",
            "Very low risk of offer withdrawal. Frames asks as 'aligning with market data'.",
            1.0,
        ),
        (
            "balanced",
            "Moderate-risk: push all components to the 65th-75th percentile range "
            "and ask for missing standard elements. This is the sweet spot for most "
            "candidates with competing offers or strong domain expertise.",
            "p75",
            "Low risk if backed by a competing offer or strong referral. "
            "Expect one round of back-and-forth.",
            1.3,
        ),
        (
            "aggressive",
            "Higher-risk: target the 80th-90th percentile on every component. "
            "Best for candidates with multiple competing offers, rare skills, "
            "or senior-level leverage.",
            "p90",
            "Moderate risk of pushback. Best when you have a written competing offer "
            "or can credibly walk away.",
            1.6,
        ),
    ]

    for name, description, salary_key, risk_note, sign_mult in tiers:
        adjustments: dict[str, str] = {}
        upside = 0.0

        # Base salary — guard against ZeroDivisionError when base_salary == 0.
        target_base = float(adj_salary_bench[salary_key])
        if target_base > base_salary:
            delta = target_base - base_salary
            if base_salary > 0:
                pct = delta / base_salary * 100
                adjustments["base_salary"] = (
                    f"Ask {_format_currency(target_base)} "
                    f"(+{_format_currency(delta)}, +{pct:.0f}%)"
                )
            else:
                adjustments["base_salary"] = (
                    f"Ask {_format_currency(target_base)} "
                    f"(+{_format_currency(delta)})"
                )
            upside += delta
        else:
            adjustments["base_salary"] = "Already at or above target — hold firm."

        # Signing bonus.
        if signing_bonus is not None:
            target_sign = float(adj_sign_bench[salary_key]) * sign_mult
            if target_sign > signing_bonus:
                delta = target_sign - signing_bonus
                adjustments["signing_bonus"] = (
                    f"Ask {_format_currency(target_sign)} "
                    f"(+{_format_currency(delta)})"
                )
                upside += delta
        else:
            # Missing signing bonus — suggest asking for one.
            suggested = float(adj_sign_bench["p50"]) * sign_mult
            adjustments["signing_bonus"] = (
                f"Request a signing bonus of {_format_currency(suggested)}"
            )
            upside += suggested

        # Equity.
        if equity is not None:
            target_ratio = equity_bench.get(salary_key, equity_bench.get("p50", 1.0))
            target_equity = target_ratio * adj_salary_bench["p50"]
            if target_equity > equity:
                delta = target_equity - equity
                adjustments["equity"] = (
                    f"Ask {_format_currency(target_equity)} total grant "
                    f"(+{_format_currency(delta)})"
                )
                # Equity is multi-year; annualize for upside calculation.
                upside += delta / 4
        elif any(m.component == "equity" for m in missing):
            suggested_ratio = equity_bench.get("p50", 0.8)
            suggested = suggested_ratio * adj_salary_bench["p50"]
            adjustments["equity"] = (
                f"Request an equity grant of ~{_format_currency(suggested)} "
                f"(4-year vest)"
            )
            upside += suggested / 4

        # Bonus %.
        if bonus_pct is not None and bonus_pct < 15:
            target_bonus = {"p50": 10, "p75": 15, "p90": 25}[salary_key]
            if target_bonus > bonus_pct:
                bonus_dollar_delta = base_salary * (target_bonus - bonus_pct) / 100
                adjustments["annual_bonus"] = (
                    f"Ask for {target_bonus}% target (currently {bonus_pct}%)"
                )
                upside += bonus_dollar_delta

        # Missing components (pick top 2 by negotiability for the strategy).
        high_neg_missing = [m for m in missing if m.negotiability == Negotiability.HIGH]
        med_neg_missing = [m for m in missing if m.negotiability == Negotiability.MEDIUM]
        ask_missing = high_neg_missing[:2] + med_neg_missing[:1]
        if name == "aggressive":
            ask_missing = high_neg_missing + med_neg_missing

        for m in ask_missing:
            if m.component not in adjustments:
                adjustments[m.component] = (
                    f"Request {m.component.replace('_', ' ')} "
                    f"(typical: {m.typical_value}). {m.note}"
                )

        strategies.append(CounterStrategy(
            name=name,
            description=description,
            adjustments=adjustments,
            estimated_upside=round(upside, 0),
            risk_note=risk_note,
        ))

    return strategies


# ---------------------------------------------------------------------------
# Text parser — extract offer details from unstructured text
# ---------------------------------------------------------------------------

# Pre-compiled regex patterns for common offer-letter formats.
_CURRENCY = r"\$[\d,]+(?:\.\d{2})?"
# Match "$150K", "150k", "$120,000", "$120,000.00" — K-suffix forms first.
_CURRENCY_OR_K = r"(?:\$[\d,]+[kK]|\$?[\d,]+[kK]|\$[\d,]+(?:\.\d{2})?)"
_PERCENT = r"\d+(?:\.\d+)?%"

_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "base_salary": [
        re.compile(
            rf"(?:base\s+(?:salary|compensation|pay)|annual\s+(?:salary|compensation))"
            rf"\s*(?:of|is|will\s+be|:)\s*({_CURRENCY_OR_K})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"({_CURRENCY_OR_K})\s*(?:per\s+(?:year|annum)|annually|/\s*(?:yr|year))",
            re.IGNORECASE,
        ),
        # Bi-weekly / semi-monthly / monthly pay periods.
        re.compile(
            rf"({_CURRENCY_OR_K})\s*(?:bi[- ]?weekly|every\s+two\s+weeks)",
            re.IGNORECASE,
        ),
        re.compile(
            rf"({_CURRENCY_OR_K})\s*(?:semi[- ]?monthly|twice\s+(?:a|per)\s+month)",
            re.IGNORECASE,
        ),
        re.compile(
            rf"({_CURRENCY_OR_K})\s*(?:per\s+month|monthly|/\s*(?:mo|month))",
            re.IGNORECASE,
        ),
        re.compile(
            rf"salary\s*(?:of|is|will\s+be|:)\s*({_CURRENCY_OR_K})",
            re.IGNORECASE,
        ),
        # Bare "Base:" without "salary" (e.g., "Base: $185,000")
        re.compile(
            rf"base\s*:\s*({_CURRENCY_OR_K})",
            re.IGNORECASE,
        ),
        # Hourly rate detection (e.g., "$85/hour", "$85/hr")
        re.compile(
            rf"({_CURRENCY_OR_K})\s*/\s*(?:hour|hr)\b",
            re.IGNORECASE,
        ),
    ],
    "signing_bonus": [
        re.compile(
            rf"sign(?:ing|[\s-]*on)\s+bonus\s*(?:of|is|:)?\s*({_CURRENCY_OR_K})",
            re.IGNORECASE,
        ),
        # Bare "Sign-on:" without "bonus" (e.g., "Sign-on: $50,000")
        re.compile(
            rf"sign[\s-]*on\s*:\s*({_CURRENCY_OR_K})",
            re.IGNORECASE,
        ),
    ],
    "equity": [
        re.compile(
            rf"(?:equity|stock|rsus?|restricted\s+stock)\s*(?:grant|award|package)?"
            rf"\s*(?:of|is|:|-|valued\s+at|worth)?\s*({_CURRENCY_OR_K})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(?:grant(?:ed)?|award(?:ed)?)\s+(?:equity|stock|rsus?|options)"
            rf"\s*(?:valued\s+at|worth|of)?\s*({_CURRENCY_OR_K})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"(\d[\d,]*)\s*(?:shares|options|rsus|units)",
            re.IGNORECASE,
        ),
    ],
    "bonus_pct": [
        re.compile(
            rf"(?:target|annual|yearly)\s+bonus\s*(?:of|is|:)?\s*({_PERCENT})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"bonus\s*(?:of|is|:)?\s*({_PERCENT})",
            re.IGNORECASE,
        ),
    ],
    "title": [
        re.compile(
            r"(?:title|position|role)\s+(?:of|is|:)\s*[\"']?"
            r"([A-Z][A-Za-z\s/&]{2,40}?)(?:[\"',.\n]|at\s|in\s)",
        ),
        re.compile(
            r"offer\s+(?:you\s+)?(?:the\s+)?(?:position|role)\s+(?:of\s+)?"
            r"([A-Z][A-Za-z\s/&]{2,40}?)(?:\s+at\s|\s+in\s|[,.\n])",
            re.IGNORECASE,
        ),
    ],
    "location": [
        re.compile(
            r"(?:location|office|based\s+(?:in|at)|work\s+from)\s*(?:is|:)?\s*"
            r"([A-Z][A-Za-z\s]{2,30}?)(?:\.|,|\n|$)",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bat\s+our\s+([A-Z][A-Za-z\s]{2,25}?)\s+office\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(remote|hybrid)\b", re.IGNORECASE),
    ],
    "start_date": [
        re.compile(
            r"(?:start\s+date|starting|begin(?:ning)?)\s*(?:is|:)?\s*"
            r"([A-Z][a-z]+\s+\d{1,2},?\s*\d{4}|\d{1,2}/\d{1,2}/\d{2,4})",
            re.IGNORECASE,
        ),
    ],
    "pto_days": [
        re.compile(
            r"(\d+)\s*(?:days?|weeks?)\s*(?:of\s+)?(?:pto|paid\s+time\s+off|vacation)",
            re.IGNORECASE,
        ),
    ],
}

# Pay-period patterns (index in _PATTERNS["base_salary"] -> annual multiplier).
# bi-weekly = index 2, semi-monthly = index 3, monthly = index 4.
_PAY_PERIOD_MULTIPLIERS: dict[int, float] = {
    2: 26.0,    # bi-weekly
    3: 24.0,    # semi-monthly
    4: 12.0,    # monthly
    7: 2080.0,  # hourly rate → annual (40hr/wk × 52wk)
}

# Role keywords for classifying from title text.
_ROLE_KEYWORDS: dict[str, list[str]] = {
    "software_engineer": [
        "software", "developer", "swe", "backend", "frontend",
        "full stack", "fullstack", "platform",
    ],
    "data_engineer": [
        "data engineer", "data engineering",
    ],
    "devops_sre": [
        "devops", "sre", "site reliability", "infrastructure engineer",
    ],
    "engineering_manager": [
        "engineering manager", "eng manager", "engineering lead",
        "director of engineering",
    ],
    "product_manager": [
        "product manager", "pm", "product lead", "product owner",
    ],
    "data_scientist": [
        "data scientist", "data analyst", "machine learning", "ml engineer",
        "analytics",
    ],
    "designer": [
        "designer", "ux", "ui", "design lead", "product designer",
        "visual designer", "interaction designer",
    ],
    "marketing_manager": [
        "marketing", "growth", "brand manager", "content manager",
        "demand gen", "marketing manager",
    ],
    "sales_representative": [
        "sales", "account executive", "ae", "bdr", "sdr",
        "business development", "account manager",
    ],
}

_LEVEL_KEYWORDS: dict[str, list[str]] = {
    "junior": ["junior", "jr", "associate", "entry", "i ", " 1 ", " l1", "new grad"],
    "mid": ["mid", "ii", " 2 ", " l2", "intermediate"],
    "senior": ["senior", "sr", "iii", " 3 ", " l3"],
    "staff": ["staff", "principal", "iv", " 4 ", " l4", "distinguished"],
    "lead": ["lead", "manager", "director", "head of", "vp"],
}


def _parse_currency(raw: str) -> float:
    """Convert '$120,000', '$120000.00', '150K', '$150k' to float."""
    cleaned = raw.replace("$", "").replace(",", "").strip()
    # Handle K/k suffix: "150K" -> 150000.0
    if cleaned.lower().endswith("k"):
        return float(cleaned[:-1]) * 1000
    return float(cleaned)


def _parse_percent(raw: str) -> float:
    """Convert '15%' to 15.0."""
    return float(raw.replace("%", ""))


def _infer_role(text: str) -> str:
    """Guess the role category from free text."""
    lower = text.lower()
    for role, keywords in _ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return role
    # Fallback: if "engineer" appears but was not caught above
    if "engineer" in lower:
        return "software_engineer"
    return "general"


def _infer_level(text: str) -> str:
    """Guess the seniority level from free text."""
    lower = text.lower()
    for level, keywords in _LEVEL_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return level
    return "mid"


def parse_offer_text(text: str) -> dict[str, Any]:
    """
    Extract structured offer details from an unstructured offer-letter string.

    Applies regex patterns for common compensation components and infers
    role/level from title keywords.  Handles "150K" format and bi-weekly /
    semi-monthly / monthly pay periods (auto-annualized).

    Parameters
    ----------
    text : str
        Raw offer-letter text (email body, PDF paste, etc.).

    Returns
    -------
    dict
        Keys match ``analyze_offer()`` parameters:
        ``role``, ``level``, ``location``, ``base_salary``, ``equity``,
        ``signing_bonus``, ``bonus_pct``, ``other_components``.
        Keys are omitted when the parser cannot find a value.
    """
    result: dict[str, Any] = {}
    other: dict[str, Any] = {}

    # Extract each component using the first matching pattern.
    for field_name, patterns in _PATTERNS.items():
        for pat_idx, pattern in enumerate(patterns):
            match = pattern.search(text)
            if match is None:
                continue
            raw = match.group(1).strip()

            if field_name == "base_salary":
                parsed = _parse_currency(raw)
                # Apply pay-period multiplier if matched a periodic pattern.
                multiplier = _PAY_PERIOD_MULTIPLIERS.get(pat_idx, 1.0)
                result["base_salary"] = parsed * multiplier
            elif field_name == "signing_bonus":
                result["signing_bonus"] = _parse_currency(raw)
            elif field_name == "equity":
                # Could be a dollar amount or a share count.
                if "$" in raw or raw.lower().endswith("k"):
                    result["equity"] = _parse_currency(raw)
                else:
                    # Store share count in other_components; can't convert to $ without price.
                    other["equity_shares"] = int(raw.replace(",", ""))
            elif field_name == "bonus_pct":
                result["bonus_pct"] = _parse_percent(raw)
            elif field_name == "title":
                other["title"] = raw.strip()
            elif field_name == "location":
                result["location"] = raw.strip()
            elif field_name == "start_date":
                other["start_date"] = raw.strip()
            elif field_name == "pto_days":
                other["pto_days"] = int(raw)
            break  # stop after first match for this field

    # Infer role and level from title or full text.
    title_text = other.get("title", "")
    context_text = f"{title_text} {text}"
    result.setdefault("role", _infer_role(context_text))
    result.setdefault("level", _infer_level(context_text))
    result.setdefault("location", "remote")

    if other:
        result["other_components"] = other

    return result
