"""Tests for persona generation."""

import pytest

from dealsim_mvp.core.persona import (
    NegotiationPersona,
    NegotiationStyle,
    PressureLevel,
    generate_persona_for_scenario,
    SALARY_NEGOTIATION_TEMPLATES,
    FREELANCE_RATE_TEMPLATES,
)


class TestGeneratePersona:
    """generate_persona_for_scenario should produce valid, scenario-appropriate personas."""

    def test_salary_scenario_returns_persona(self):
        persona = generate_persona_for_scenario(
            {"type": "salary", "target_value": 100_000, "difficulty": "medium"}
        )
        assert isinstance(persona, NegotiationPersona)

    def test_freelance_scenario_returns_persona(self):
        persona = generate_persona_for_scenario(
            {"type": "freelance", "target_value": 150, "difficulty": "medium"}
        )
        assert isinstance(persona, NegotiationPersona)

    def test_unknown_type_falls_back_to_salary(self):
        persona = generate_persona_for_scenario(
            {"type": "procurement", "target_value": 50_000, "difficulty": "medium"}
        )
        assert isinstance(persona, NegotiationPersona)
        salary_names = {t(100_000).name for t in SALARY_NEGOTIATION_TEMPLATES.values()}
        assert persona.name in salary_names

    def test_default_scenario_when_none(self):
        persona = generate_persona_for_scenario({})
        assert isinstance(persona, NegotiationPersona)


class TestPersonaFieldsPopulated:
    """Every persona field should be populated with a valid value."""

    @pytest.fixture(params=["salary", "freelance"])
    def persona(self, request):
        return generate_persona_for_scenario(
            {"type": request.param, "target_value": 100_000, "difficulty": "medium"}
        )

    def test_name_is_nonempty_string(self, persona):
        assert isinstance(persona.name, str) and len(persona.name) > 0

    def test_role_is_nonempty_string(self, persona):
        assert isinstance(persona.role, str) and len(persona.role) > 0

    def test_style_is_valid_enum(self, persona):
        assert isinstance(persona.style, NegotiationStyle)

    def test_pressure_is_valid_enum(self, persona):
        assert isinstance(persona.pressure, PressureLevel)

    def test_patience_in_range(self, persona):
        assert 0.0 <= persona.patience <= 1.0

    def test_transparency_in_range(self, persona):
        assert 0.0 <= persona.transparency <= 1.0

    def test_emotional_reactivity_in_range(self, persona):
        assert 0.0 <= persona.emotional_reactivity <= 1.0

    def test_target_price_positive(self, persona):
        assert persona.target_price > 0

    def test_reservation_price_positive(self, persona):
        assert persona.reservation_price > 0

    def test_opening_offer_positive(self, persona):
        assert persona.opening_offer > 0

    def test_hidden_constraints_is_list(self, persona):
        assert isinstance(persona.hidden_constraints, list)
        assert all(isinstance(c, str) for c in persona.hidden_constraints)


class TestDifficultyAdjustment:
    """Difficulty setting should adjust persona traits."""

    def test_hard_reduces_patience(self):
        easy = generate_persona_for_scenario(
            {"type": "salary", "target_value": 100_000, "difficulty": "easy"}
        )
        hard = generate_persona_for_scenario(
            {"type": "salary", "target_value": 100_000, "difficulty": "hard"}
        )
        assert hard.patience <= easy.patience

    def test_hard_tightens_reservation(self):
        import random
        # Fix seed to ensure both calls pick the same template
        random.seed(42)
        medium = generate_persona_for_scenario(
            {"type": "salary", "target_value": 100_000, "difficulty": "medium"}
        )
        random.seed(42)
        hard = generate_persona_for_scenario(
            {"type": "salary", "target_value": 100_000, "difficulty": "hard"}
        )
        assert hard.reservation_price <= medium.reservation_price

    def test_easy_increases_reservation(self):
        import random
        random.seed(42)
        medium = generate_persona_for_scenario(
            {"type": "salary", "target_value": 100_000, "difficulty": "medium"}
        )
        random.seed(42)
        easy = generate_persona_for_scenario(
            {"type": "salary", "target_value": 100_000, "difficulty": "easy"}
        )
        assert easy.reservation_price >= medium.reservation_price


class TestDifferentScenariosProduceDifferentPersonas:
    """Salary and freelance scenarios should produce different persona pools."""

    def test_freelance_persona_has_budget_client_traits(self):
        persona = generate_persona_for_scenario(
            {"type": "freelance", "target_value": 100, "difficulty": "medium"}
        )
        freelance_names = {t(100).name for t in FREELANCE_RATE_TEMPLATES.values()}
        assert persona.name in freelance_names

    def test_salary_persona_has_salary_names(self):
        persona = generate_persona_for_scenario(
            {"type": "salary", "target_value": 100_000, "difficulty": "medium"}
        )
        salary_names = {t(100_000).name for t in SALARY_NEGOTIATION_TEMPLATES.values()}
        assert persona.name in salary_names


class TestMirofishConfig:
    """to_mirofish_config should return a well-formed dict."""

    def test_config_has_required_keys(self, salary_persona):
        config = salary_persona.to_mirofish_config()
        assert "name" in config
        assert "personality" in config
        assert "constraints" in config
        assert "system_prompt" in config

    def test_config_personality_values(self, salary_persona):
        config = salary_persona.to_mirofish_config()
        assert config["personality"]["negotiation_style"] == "collaborative"
        assert config["personality"]["pressure_level"] == "medium"

    def test_config_constraints_has_hidden(self, salary_persona):
        config = salary_persona.to_mirofish_config()
        assert isinstance(config["constraints"]["hidden"], list)
        assert len(config["constraints"]["hidden"]) > 0
