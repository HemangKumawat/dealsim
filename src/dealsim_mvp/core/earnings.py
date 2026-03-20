"""
Lifetime earnings impact calculator.

Shows users the compounding financial impact of negotiating a higher salary
today, including salary growth with annual raises and the retirement
multiplier effect (employer match + investment returns).

Math:
  - Salary difference in year *n* = negotiated_increase * (1 + raise_rate)^n
  - Retirement contribution per year = salary_diff * contribution_rate
  - Employer match per year = min(contribution, salary_diff * match_rate)
  - Retirement balance grows at investment_return_pct annually (compound)

All monetary values are in the same currency as *current_salary*.

Example
-------
>>> impact = calculate_lifetime_impact(80_000, 10_000, years_to_retirement=30)
>>> impact.total_lifetime_impact > 600_000
True
>>> len(impact.year_by_year) == 30
True
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class YearBreakdown:
    """Single-year snapshot of the negotiation's financial impact."""
    year: int
    salary_difference: float        # extra salary earned this year
    cumulative_salary: float        # total extra salary earned through this year
    retirement_contribution: float  # employee contribution from the raise
    employer_match: float           # employer's matching contribution
    retirement_balance: float       # running retirement balance (with returns)


@dataclass
class EarningsImpact:
    """Full lifetime impact of a salary negotiation."""
    negotiated_increase: float
    years: int
    total_salary_difference: float          # cumulative extra salary (with raises)
    total_with_raises: float                # same as above (alias kept for clarity)
    retirement_impact: float                # additional retirement savings
    total_lifetime_impact: float            # salary + retirement
    year_by_year: list[YearBreakdown] = field(default_factory=list)
    key_insight: str = ""


# ---------------------------------------------------------------------------
# Core calculator
# ---------------------------------------------------------------------------

def calculate_lifetime_impact(
    current_salary: float,
    negotiated_increase: float,
    years_to_retirement: int = 30,
    annual_raise_pct: float = 3.0,
    retirement_contribution_pct: float = 10.0,
    employer_match_pct: float = 50.0,
    investment_return_pct: float = 7.0,
) -> EarningsImpact:
    """
    Calculate the compounding lifetime impact of negotiating more salary today.

    Parameters
    ----------
    current_salary : float
        Current annual salary (used only for context; the increase is absolute).
    negotiated_increase : float
        Additional annual salary secured through negotiation (e.g. 10_000).
    years_to_retirement : int
        Number of working years remaining (default 30).
    annual_raise_pct : float
        Expected annual raise as a percentage (default 3.0 means 3%).
    retirement_contribution_pct : float
        Percentage of salary contributed to retirement (default 10%).
    employer_match_pct : float
        Employer match as a percentage of employee contribution (default 50%).
    investment_return_pct : float
        Expected annual investment return in retirement account (default 7%).

    Returns
    -------
    EarningsImpact
        Detailed breakdown including year-by-year figures and a headline insight.

    Examples
    --------
    >>> impact = calculate_lifetime_impact(80_000, 10_000, years_to_retirement=5,
    ...     annual_raise_pct=0.0, retirement_contribution_pct=10.0,
    ...     employer_match_pct=50.0, investment_return_pct=0.0)
    >>> impact.total_salary_difference
    50000.0
    >>> impact.retirement_impact
    7500.0

    >>> impact = calculate_lifetime_impact(80_000, 10_000, years_to_retirement=1,
    ...     annual_raise_pct=0.0, retirement_contribution_pct=10.0,
    ...     employer_match_pct=100.0, investment_return_pct=0.0)
    >>> impact.retirement_impact
    2000.0
    """
    raise_rate = annual_raise_pct / 100.0
    contrib_rate = retirement_contribution_pct / 100.0
    match_rate = employer_match_pct / 100.0
    invest_rate = investment_return_pct / 100.0

    year_by_year: list[YearBreakdown] = []
    cumulative_salary = 0.0
    retirement_balance = 0.0

    for n in range(years_to_retirement):
        # The raise compounds: in year n the salary difference is larger
        salary_diff = negotiated_increase * (1 + raise_rate) ** n

        cumulative_salary += salary_diff

        # Employee retirement contribution from the extra salary
        employee_contrib = salary_diff * contrib_rate
        # Employer matches a percentage of the employee contribution
        employer_contrib = employee_contrib * match_rate

        # Existing balance grows, then new contributions are added (end-of-year)
        retirement_balance = retirement_balance * (1 + invest_rate) + employee_contrib + employer_contrib

        year_by_year.append(YearBreakdown(
            year=n + 1,
            salary_difference=round(salary_diff, 2),
            cumulative_salary=round(cumulative_salary, 2),
            retirement_contribution=round(employee_contrib, 2),
            employer_match=round(employer_contrib, 2),
            retirement_balance=round(retirement_balance, 2),
        ))

    total_salary = round(cumulative_salary, 2)
    retirement = round(retirement_balance, 2)
    total = round(total_salary + retirement, 2)

    key_insight = (
        f"Negotiating ${negotiated_increase:,.0f} more today = "
        f"${total:,.0f} over {years_to_retirement} years"
    )

    return EarningsImpact(
        negotiated_increase=negotiated_increase,
        years=years_to_retirement,
        total_salary_difference=total_salary,
        total_with_raises=total_salary,
        retirement_impact=retirement,
        total_lifetime_impact=total,
        year_by_year=year_by_year,
        key_insight=key_insight,
    )


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def format_impact_summary(impact: EarningsImpact) -> str:
    """Return a human-readable multi-line summary suitable for display."""
    lines = [
        impact.key_insight,
        "",
        f"  Extra salary (with raises):   ${impact.total_salary_difference:>12,.2f}",
        f"  Retirement multiplier effect:  ${impact.retirement_impact:>12,.2f}",
        f"  -----------------------------------------",
        f"  TOTAL LIFETIME IMPACT:         ${impact.total_lifetime_impact:>12,.2f}",
        "",
        "Year-by-year highlights:",
    ]

    milestones = {1, 5, 10, 15, 20, 25, 30}
    for yb in impact.year_by_year:
        if yb.year in milestones or yb.year == impact.years:
            lines.append(
                f"  Year {yb.year:>2}: "
                f"+${yb.salary_difference:>10,.2f} salary  |  "
                f"${yb.retirement_balance:>12,.2f} retirement balance"
            )

    return "\n".join(lines)
