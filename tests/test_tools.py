"""Tests for earnings calculator and email audit (core modules)."""

import pytest

from dealsim_mvp.core.earnings import (
    EarningsImpact,
    YearBreakdown,
    calculate_lifetime_impact,
    format_impact_summary,
)
from dealsim_mvp.core.email_audit import (
    EmailAudit,
    Issue,
    Severity,
    audit_negotiation_email,
)


# ===========================================================================
# Earnings calculator
# ===========================================================================

class TestEarningsCalculator:
    """calculate_lifetime_impact should compute compounding salary differences."""

    def test_basic_calculation(self):
        impact = calculate_lifetime_impact(80_000, 10_000, years_to_retirement=30)
        assert isinstance(impact, EarningsImpact)
        assert impact.total_lifetime_impact > 600_000
        assert len(impact.year_by_year) == 30

    def test_zero_increase(self):
        impact = calculate_lifetime_impact(100_000, 0, years_to_retirement=10)
        assert impact.total_salary_difference == 0.0
        assert impact.retirement_impact == 0.0
        assert impact.total_lifetime_impact == 0.0

    def test_one_year(self):
        impact = calculate_lifetime_impact(
            80_000, 10_000, years_to_retirement=1,
            annual_raise_pct=0.0, retirement_contribution_pct=10.0,
            employer_match_pct=100.0, investment_return_pct=0.0,
        )
        assert impact.total_salary_difference == 10_000.0
        # 10% contrib = 1000, 100% match = 1000, total retirement = 2000
        assert impact.retirement_impact == 2_000.0

    def test_five_years_no_raises(self):
        impact = calculate_lifetime_impact(
            80_000, 10_000, years_to_retirement=5,
            annual_raise_pct=0.0, retirement_contribution_pct=10.0,
            employer_match_pct=50.0, investment_return_pct=0.0,
        )
        assert impact.total_salary_difference == 50_000.0
        # Each year: contrib=1000, match=500 => 1500/yr => 7500 total
        assert impact.retirement_impact == 7_500.0

    def test_year_by_year_correct_length(self):
        impact = calculate_lifetime_impact(80_000, 5_000, years_to_retirement=20)
        assert len(impact.year_by_year) == 20

    def test_year_by_year_first_entry(self):
        impact = calculate_lifetime_impact(
            80_000, 10_000, years_to_retirement=5,
            annual_raise_pct=0.0, retirement_contribution_pct=0.0,
            employer_match_pct=0.0, investment_return_pct=0.0,
        )
        first = impact.year_by_year[0]
        assert first.year == 1
        assert first.salary_difference == 10_000.0
        assert first.cumulative_salary == 10_000.0

    def test_compounding_with_raises(self):
        impact = calculate_lifetime_impact(
            80_000, 10_000, years_to_retirement=2,
            annual_raise_pct=10.0, retirement_contribution_pct=0.0,
            employer_match_pct=0.0, investment_return_pct=0.0,
        )
        # Year 1: 10000, Year 2: 10000 * 1.1 = 11000 => total = 21000
        assert impact.total_salary_difference == pytest.approx(21_000.0, rel=0.01)

    def test_key_insight_populated(self):
        impact = calculate_lifetime_impact(80_000, 10_000)
        assert len(impact.key_insight) > 0


class TestFormatImpactSummary:
    def test_returns_string(self):
        impact = calculate_lifetime_impact(80_000, 10_000, years_to_retirement=5)
        text = format_impact_summary(impact)
        assert isinstance(text, str)
        assert "TOTAL LIFETIME IMPACT" in text


# ===========================================================================
# Email audit
# ===========================================================================

class TestEmailAudit:
    """audit_negotiation_email should detect common weaknesses."""

    def test_strong_email_scores_high(self):
        email = (
            "Thank you for the offer -- I'm excited about the role. "
            "Based on my research, comparable positions pay $95,000. "
            "I've contributed $200K in revenue this year. "
            "I'd like to discuss a base salary of $95,000. "
            "Can we find 15 minutes this week?"
        )
        result = audit_negotiation_email(email)
        assert isinstance(result, EmailAudit)
        assert result.score >= 80
        assert len(result.strengths) >= 2

    def test_weak_email_scores_low(self):
        email = (
            "Hi, I was hoping if possible to maybe get a raise. "
            "Sorry to ask but I feel like I deserve more."
        )
        result = audit_negotiation_email(email)
        assert result.score < 50
        hedging_issues = [i for i in result.issues if i.issue_type == "hedging"]
        assert len(hedging_issues) >= 3

    def test_detects_missing_anchor(self):
        email = "I think I should earn more based on my experience."
        result = audit_negotiation_email(email)
        anchor_issues = [i for i in result.issues if i.issue_type == "missing_anchor"]
        assert len(anchor_issues) == 1

    def test_detects_missing_justification(self):
        email = "I want $120,000."
        result = audit_negotiation_email(email)
        just_issues = [i for i in result.issues if i.issue_type == "missing_justification"]
        assert len(just_issues) == 1

    def test_detects_emotional_language(self):
        email = "I feel unfair and disrespected by this offer."
        result = audit_negotiation_email(email)
        emotional = [i for i in result.issues if i.issue_type == "emotional_language"]
        assert len(emotional) >= 1

    def test_detects_passive_voice(self):
        email = "It would be appreciated if my salary could be increased to $100,000."
        result = audit_negotiation_email(email)
        passive = [i for i in result.issues if i.issue_type == "passive_voice"]
        assert len(passive) >= 1

    def test_too_long_email(self):
        email = "Word " * 350
        result = audit_negotiation_email(email)
        length_issues = [i for i in result.issues if i.issue_type == "too_long"]
        assert len(length_issues) == 1

    def test_too_short_email(self):
        email = "Hi."
        result = audit_negotiation_email(email)
        length_issues = [i for i in result.issues if i.issue_type == "too_short"]
        assert len(length_issues) == 1

    def test_rewritten_version_removes_hedging(self):
        email = "I was hoping if possible to get a raise to $100,000."
        result = audit_negotiation_email(email)
        assert "i was hoping" not in result.rewritten_version.lower()
        assert "if possible" not in result.rewritten_version.lower()

    def test_score_never_negative(self):
        """Even the worst email should score >= 0."""
        email = (
            "Sorry to ask, I was hoping if possible, perhaps, "
            "I was wondering if you could maybe, no worries if not, "
            "just wondering, I don't want to be pushy, I hate to ask, "
            "if it's not too much trouble, I might be wrong but "
            "it was suggested that I feel like it would be appreciated."
        )
        result = audit_negotiation_email(email)
        assert result.score >= 0

    def test_score_never_above_100(self):
        email = (
            "Thank you for the offer. I'm excited about the role. "
            "Based on my research, comparable roles pay $150,000. "
            "Market data shows the value I bring is significant. "
            "I've contributed major revenue. My track record speaks for itself. "
            "I'm confident that $150,000 is fair. "
            "I'd like to discuss a salary of $150,000. "
            "Can we schedule a call?"
        )
        result = audit_negotiation_email(email)
        assert result.score <= 100


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEmailEdgeCases:
    def test_empty_string(self):
        result = audit_negotiation_email("")
        assert isinstance(result, EmailAudit)
        assert result.score >= 0

    def test_unicode_and_emoji(self):
        email = "I'd like $120,000 please. Based on my research 🙏 this is fair."
        result = audit_negotiation_email(email)
        assert isinstance(result, EmailAudit)

    def test_extremely_long_input(self):
        email = "Please raise my salary to $100,000. " * 500
        result = audit_negotiation_email(email)
        assert isinstance(result, EmailAudit)
