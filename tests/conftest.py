"""Shared fixtures for DealSim MVP tests."""

import pytest
from fastapi.testclient import TestClient

from dealsim_mvp.core.persona import (
    NegotiationPersona,
    NegotiationStyle,
    PressureLevel,
)
from dealsim_mvp.core.simulator import (
    NegotiationState,
    RuleBasedSimulator,
)
from dealsim_mvp.core.session import _SESSIONS
from dealsim_mvp.core.store import clear_store
from dealsim_mvp.app import app
import dealsim_mvp.rate_limiter as _rl


# ---------------------------------------------------------------------------
# Persona fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def salary_persona() -> NegotiationPersona:
    """A deterministic collaborative salary persona for testing."""
    return NegotiationPersona(
        name="Test Recruiter",
        role="HR Director",
        style=NegotiationStyle.COLLABORATIVE,
        pressure=PressureLevel.MEDIUM,
        target_price=85_000,
        reservation_price=115_000,
        opening_offer=80_000,
        patience=0.7,
        transparency=0.5,
        emotional_reactivity=0.3,
        hidden_constraints=["Budget ceiling is 120K"],
    )


@pytest.fixture
def competitive_persona() -> NegotiationPersona:
    """A competitive persona that concedes slowly."""
    return NegotiationPersona(
        name="Tough Negotiator",
        role="Procurement Manager",
        style=NegotiationStyle.COMPETITIVE,
        pressure=PressureLevel.LOW,
        target_price=70_000,
        reservation_price=105_000,
        opening_offer=75_000,
        patience=0.3,
        transparency=0.2,
        emotional_reactivity=0.5,
        hidden_constraints=["Can go up to 105K but will resist"],
    )


@pytest.fixture
def accommodating_persona() -> NegotiationPersona:
    """An accommodating persona that yields easily."""
    return NegotiationPersona(
        name="Friendly Manager",
        role="Startup Founder",
        style=NegotiationStyle.ACCOMMODATING,
        pressure=PressureLevel.HIGH,
        target_price=90_000,
        reservation_price=120_000,
        opening_offer=85_000,
        patience=0.8,
        transparency=0.7,
        emotional_reactivity=0.2,
        hidden_constraints=[],
    )


# ---------------------------------------------------------------------------
# Simulator fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simulator() -> RuleBasedSimulator:
    return RuleBasedSimulator()


@pytest.fixture
def negotiation_state(salary_persona, simulator) -> NegotiationState:
    """A state with the opening turn already played."""
    state = simulator.initialize_state(salary_persona)
    simulator.opening_statement(state)
    return state


# ---------------------------------------------------------------------------
# API fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """FastAPI TestClient -- clears session store between tests."""
    _SESSIONS.clear()
    clear_store()
    with TestClient(app) as c:
        yield c
    _SESSIONS.clear()
    clear_store()


# ---------------------------------------------------------------------------
# Session cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_sessions():
    """Ensure both in-memory and on-disk session stores are clean before/after every test."""
    _SESSIONS.clear()
    clear_store()
    _rl._BUCKETS.clear()
    yield
    _SESSIONS.clear()
    clear_store()
    _rl._BUCKETS.clear()
