"""Tests for offer analysis (core and API layers)."""

import pytest

from dealsim_mvp.core.offer_analyzer import (
    OfferAnalysis,
    PercentilePosition,
    MissingComponent,
    CounterStrategy,
    analyze_offer,
    parse_offer_text,
    _normalize_key,
    _estimate_percentile,
    _ordinal,
)
from dealsim_mvp.api.offer_analyzer import (
    analyze_offer as api_analyze_offer,
    get_market_data,
    get_available_roles,
    get_available_locations,
    calculate_earnings_impact,
    audit_email,
    MarketData,
    EarningsImpact,
    EmailAudit,
)


# ---------------------------------------------------------------------------
# Core offer analyzer
# ---------------------------------------------------------------------------

class TestAnalyzeOffer:
    """analyze_offer should return a complete OfferAnalysis."""

    def test_basic_salary_analysis(self):
        result = analyze_offer(
            role="software_engineer", level="senior",
            location="san_francisco", base_salary=160_000,
        )
        assert isinstance(result, OfferAnalysis)
        assert len(result.percentile_positions) >= 1
        assert result.location_multiplier > 0

    def test_with_equity_and_bonus(self):
        result = analyze_offer(
            role="software_engineer", level="mid",
            location="austin", base_salary=120_000,
            equity=50_000, signing_bonus=15_000, bonus_pct=10,
        )
        assert len(result.percentile_positions) == 4  # base, equity, signing, bonus

    def test_missing_components_detected(self):
        result = analyze_offer(
            role="general", level="mid",
            location="remote", base_salary=90_000,
        )
        missing_names = [m.component for m in result.missing_components]
        assert "signing_bonus" in missing_names
        assert "equity" in missing_names

    def test_counter_strategies_generated(self):
        result = analyze_offer(
            role="software_engineer", level="senior",
            location="new_york", base_salary=140_000,
        )
        assert len(result.counter_strategies) == 3
        names = [s.name for s in result.counter_strategies]
        assert "conservative" in names
        assert "balanced" in names
        assert "aggressive" in names

    def test_total_potential_upside_positive(self):
        result = analyze_offer(
            role="software_engineer", level="senior",
            location="san_francisco", base_salary=100_000,
        )
        # Below-market salary => upside should be positive
        assert result.total_potential_upside > 0

    def test_unknown_role_falls_back_to_general(self):
        result = analyze_offer(
            role="unicorn_rider", level="mid",
            location="remote", base_salary=90_000,
        )
        assert isinstance(result, OfferAnalysis)

    def test_market_comparison_text(self):
        result = analyze_offer(
            role="software_engineer", level="mid",
            location="austin", base_salary=120_000,
        )
        assert "percentile" in result.market_comparison.lower()


# ---------------------------------------------------------------------------
# Text parser
# ---------------------------------------------------------------------------

class TestParseOfferText:
    """parse_offer_text should extract structured data from raw text."""

    def test_extracts_base_salary(self):
        text = "We're offering a base salary of $130,000 per year."
        result = parse_offer_text(text)
        assert "base_salary" in result
        assert result["base_salary"] == pytest.approx(130_000)

    def test_extracts_signing_bonus(self):
        text = "Signing bonus of $20,000."
        result = parse_offer_text(text)
        assert "signing_bonus" in result
        assert result["signing_bonus"] == pytest.approx(20_000)

    def test_extracts_bonus_pct(self):
        text = "Target bonus of 15%."
        result = parse_offer_text(text)
        assert "bonus_pct" in result
        assert result["bonus_pct"] == pytest.approx(15.0)

    def test_infers_role_from_title(self):
        text = "We're offering the Senior Software Engineer position with a salary of $150,000."
        result = parse_offer_text(text)
        assert result["role"] == "software_engineer"
        assert result["level"] == "senior"

    def test_defaults_location_to_remote(self):
        text = "Salary: $100,000"
        result = parse_offer_text(text)
        assert result["location"] == "remote"

    def test_empty_text(self):
        result = parse_offer_text("")
        assert "role" in result
        assert result.get("location") == "remote"

    def test_parses_150k_format(self):
        text = "Base salary of $150K per year."
        result = parse_offer_text(text)
        assert "base_salary" in result
        assert result["base_salary"] == pytest.approx(150_000)

    def test_parses_biweekly_pay(self):
        text = "You will be paid $5,000 bi-weekly."
        result = parse_offer_text(text)
        assert "base_salary" in result
        assert result["base_salary"] == pytest.approx(130_000)

    def test_parses_monthly_pay(self):
        text = "Your compensation is $12,500 per month."
        result = parse_offer_text(text)
        assert "base_salary" in result
        assert result["base_salary"] == pytest.approx(150_000)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_normalize_key(self):
        assert _normalize_key("San Francisco") == "san_francisco"
        assert _normalize_key("New-York") == "new_york"

    def test_estimate_percentile_at_median(self):
        bench = {"p25": 80_000, "p50": 100_000, "p75": 120_000, "p90": 140_000}
        pctl = _estimate_percentile(100_000, bench)
        assert pctl == 50

    def test_estimate_percentile_low(self):
        bench = {"p25": 80_000, "p50": 100_000, "p75": 120_000, "p90": 140_000}
        pctl = _estimate_percentile(50_000, bench)
        assert pctl == 0

    def test_estimate_percentile_high(self):
        bench = {"p25": 80_000, "p50": 100_000, "p75": 120_000, "p90": 140_000}
        pctl = _estimate_percentile(200_000, bench)
        assert pctl == 100

    def test_ordinal(self):
        assert _ordinal(1) == "1st"
        assert _ordinal(2) == "2nd"
        assert _ordinal(3) == "3rd"
        assert _ordinal(11) == "11th"
        assert _ordinal(21) == "21st"


# ---------------------------------------------------------------------------
# API-level offer analyzer
# ---------------------------------------------------------------------------

class TestAPIOfferAnalyzer:

    def test_analyze_offer_from_text(self):
        # Use plain text that avoids signing/bonus regex collision bugs
        result = api_analyze_offer("Base salary $130k, 4 weeks PTO, remote work")
        assert hasattr(result, "components")
        assert hasattr(result, "overall_score")
        assert result.overall_score >= 0

    def test_analyze_offer_combined_bonus_format(self):
        """Previously crashed with ValueError due to regex group collision.
        Now fixed — should parse both bonus types without error."""
        result = api_analyze_offer("Base salary $130k, 15% annual bonus, $10k signing bonus")
        assert hasattr(result, "components")
        comp_names = [c.name for c in result.components]
        assert "base_salary" in comp_names
        assert "signing_bonus" in comp_names

    def test_get_market_data_known_role(self):
        data = get_market_data("software_engineer", "san_francisco")
        assert isinstance(data, MarketData)
        assert data.p50 > 0

    def test_get_market_data_unknown_role(self):
        data = get_market_data("nonexistent_role", "san_francisco")
        assert data is None

    def test_get_available_roles(self):
        roles = get_available_roles()
        assert "software_engineer" in roles

    def test_get_available_locations(self):
        locs = get_available_locations("software_engineer")
        assert "san_francisco" in locs

    def test_calculate_earnings_impact(self):
        impact = calculate_earnings_impact(100_000, 115_000)
        assert isinstance(impact, EarningsImpact)
        assert impact.difference_annual == 15_000
        assert impact.difference_5yr > impact.difference_annual * 5  # compounding
        assert impact.difference_career > 0

    def test_audit_email_strong(self):
        email = (
            "Thank you for the offer -- I'm excited about the role. "
            "Based on my research, comparable positions pay $125,000. "
            "I'd like to discuss a base salary of $125,000."
        )
        result = audit_email(email)
        assert isinstance(result, EmailAudit)
        assert result.overall_score >= 60

    def test_audit_email_weak(self):
        email = "Sorry to bother you, I was just wondering if maybe you could pay me more?"
        result = audit_email(email)
        assert result.overall_score < 50
        assert len(result.issues) > 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestOfferEdgeCases:

    def test_zero_base_salary_raises_value_error(self):
        """Zero base salary now raises ValueError (bounds check) instead of
        ZeroDivisionError."""
        with pytest.raises(ValueError):
            analyze_offer(
                role="general", level="mid", location="remote", base_salary=0,
            )

    def test_negative_salary_raises_value_error(self):
        with pytest.raises(ValueError, match="(?i)negative"):
            analyze_offer(
                role="general", level="mid", location="remote", base_salary=-50_000,
            )

    def test_excessive_salary_raises_value_error(self):
        with pytest.raises(ValueError, match="base_salary must be <="):
            analyze_offer(
                role="general", level="mid", location="remote", base_salary=20_000_000,
            )

    def test_very_high_salary(self):
        result = analyze_offer(
            role="software_engineer", level="staff",
            location="san_francisco", base_salary=500_000,
        )
        assert result.percentile_positions[0].percentile >= 90

    def test_earnings_impact_same_salary(self):
        impact = calculate_earnings_impact(100_000, 100_000)
        assert impact.difference_annual == 0
        assert impact.difference_career == 0

    def test_new_roles_exist(self):
        """Verify the three new roles have benchmark data."""
        for role in ("data_engineer", "devops_sre", "engineering_manager"):
            result = analyze_offer(
                role=role, level="senior", location="remote", base_salary=170_000,
            )
            assert isinstance(result, OfferAnalysis)

    def test_new_locations_exist(self):
        """Verify the four new locations have multipliers."""
        for loc in ("miami", "philadelphia", "pittsburgh", "raleigh"):
            result = analyze_offer(
                role="software_engineer", level="mid", location=loc, base_salary=120_000,
            )
            assert result.location_multiplier != 1.0 or loc == "raleigh"
