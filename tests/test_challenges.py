"""Tests for the daily challenge system."""

import pytest
from datetime import date

from dealsim_mvp.core.challenges import (
    DailyChallenge,
    get_daily_challenge,
    get_challenge_by_category,
    list_categories,
    list_all_challenges,
)
from dealsim_mvp.core.persona import NegotiationPersona, NegotiationStyle
from dealsim_mvp.api.analytics import (
    get_todays_challenge,
    submit_challenge_response,
    CHALLENGE_POOL,
)


# ---------------------------------------------------------------------------
# Core challenge system
# ---------------------------------------------------------------------------

class TestGetDailyChallenge:
    """get_daily_challenge returns a valid DailyChallenge."""

    def test_returns_daily_challenge(self):
        c = get_daily_challenge(day=1)
        assert isinstance(c, DailyChallenge)

    def test_day_1_is_anchoring(self):
        c = get_daily_challenge(day=1)
        assert c.category == "Anchoring"
        assert c.day == 1

    def test_day_30_exists(self):
        c = get_daily_challenge(day=30)
        assert c.day == 30

    def test_clamps_below_1(self):
        c = get_daily_challenge(day=0)
        assert c.day == 1

    def test_clamps_above_30(self):
        c = get_daily_challenge(day=50)
        assert c.day == 30

    def test_none_uses_today(self):
        c = get_daily_challenge(day=None)
        expected_day = (date.today().toordinal() % 30) + 1
        assert c.day == expected_day

    def test_all_30_days_valid(self):
        for d in range(1, 31):
            c = get_daily_challenge(day=d)
            assert isinstance(c, DailyChallenge)
            assert c.day == d
            assert c.max_exchanges == 3


class TestChallengeFields:
    """Every challenge should have fully populated fields."""

    @pytest.mark.parametrize("day", range(1, 31))
    def test_fields_populated(self, day):
        c = get_daily_challenge(day=day)
        assert len(c.title) > 0
        assert len(c.category) > 0
        assert len(c.scoring_focus) > 0
        assert len(c.setup) > 0
        assert len(c.success_hint) > 0
        assert isinstance(c.opponent, NegotiationPersona)
        assert isinstance(c.opponent.style, NegotiationStyle)


class TestGetChallengeByCategory:
    def test_anchoring_returns_five(self):
        anchoring = get_challenge_by_category("Anchoring")
        assert len(anchoring) == 5

    def test_case_insensitive(self):
        result = get_challenge_by_category("anchoring")
        assert len(result) == 5

    def test_unknown_category_returns_empty(self):
        result = get_challenge_by_category("Nonexistent")
        assert result == []

    def test_all_categories_have_challenges(self):
        cats = list_categories()
        for cat in cats:
            result = get_challenge_by_category(cat)
            assert len(result) >= 1, f"Category '{cat}' has no challenges"


class TestListCategories:
    def test_returns_six_categories(self):
        cats = list_categories()
        assert len(cats) == 6

    def test_contains_anchoring(self):
        cats = list_categories()
        assert "Anchoring" in cats

    def test_order_is_deterministic(self):
        cats1 = list_categories()
        cats2 = list_categories()
        assert cats1 == cats2


class TestListAllChallenges:
    def test_returns_30_entries(self):
        all_c = list_all_challenges()
        assert len(all_c) == 30

    def test_each_entry_has_metadata(self):
        for entry in list_all_challenges():
            assert "day" in entry
            assert "title" in entry
            assert "category" in entry
            assert "scoring_focus" in entry


# ---------------------------------------------------------------------------
# API challenge system
# ---------------------------------------------------------------------------

class TestAPIChallenges:
    """Tests for the API-layer challenge functions in api.analytics."""

    def test_get_todays_challenge_returns_dict(self):
        c = get_todays_challenge()
        assert isinstance(c, dict)
        assert "id" in c
        assert "title" in c
        assert "scoring_criteria" in c
        assert "date" in c

    def test_submit_with_strong_response(self):
        result = submit_challenge_response(
            "test_user",
            "Based on my research, I'd like $135,000. I have another offer at $125,000 "
            "and I'm excited about the opportunity. The market data supports this number."
        )
        assert "total" in result
        assert "breakdown" in result
        assert result["total"] >= 0
        assert result["total"] <= 100

    def test_submit_with_empty_response(self):
        """Even a minimal response should not crash."""
        result = submit_challenge_response("test_user", "Hello there.")
        assert "total" in result
        assert result["total"] >= 0

    def test_submit_with_numbers(self):
        """Response with numbers should produce a valid score."""
        result = submit_challenge_response(
            "test_user",
            "I'd like $140,000 because the market data supports it. "
            "I'm excited about this opportunity and looking forward to contributing."
        )
        # Should produce a valid score (exact criteria depend on today's challenge)
        assert result["total"] >= 0
        assert result["total"] <= 100

    def test_challenge_pool_has_entries(self):
        assert len(CHALLENGE_POOL) >= 5


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestChallengeEdgeCases:
    """Edge cases for the challenge system."""

    def test_negative_day(self):
        c = get_daily_challenge(day=-5)
        assert c.day == 1

    def test_unicode_in_response(self):
        result = submit_challenge_response("user", "I'd like $130,000 🎯 based on research.")
        assert "total" in result

    def test_very_long_response(self):
        long_text = "I want $150,000 because of my experience. " * 200
        result = submit_challenge_response("user", long_text)
        assert "total" in result
