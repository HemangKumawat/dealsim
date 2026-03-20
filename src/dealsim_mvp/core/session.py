"""
Session manager for DealSim negotiation sessions.

Lifecycle:
  create_session() → negotiate() [repeated] → complete_session() → Scorecard

State is stored in-memory (dict) for the MVP.  The interface is designed
so replacing the in-memory store with Redis or a DB requires only changing
``_SESSIONS`` and the two store/load helpers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import logging
import threading

from dealsim_mvp.core.persona import NegotiationPersona, generate_persona_for_scenario
from dealsim_mvp.core.scorer import Scorecard, generate_scorecard
from dealsim_mvp.core.simulator import (
    NegotiationState,
    RuleBasedSimulator,
    SimulatorBase,
    Turn,
)
from dealsim_mvp.core.store import save_session, load_session, load_all_sessions

# Conditional import — LLMSimulator may not be installed in all environments
try:
    from dealsim_mvp.core.llm_simulator import LLMSimulator as _LLMSimulator
except ImportError:
    _LLMSimulator = None  # type: ignore[misc,assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session types
# ---------------------------------------------------------------------------

class SessionStatus(str, Enum):
    ACTIVE    = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class NegotiationSession:
    """Container for a live negotiation session."""
    session_id: str
    persona: NegotiationPersona
    state: NegotiationState
    simulator: SimulatorBase
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime  = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    scorecard: Scorecard | None   = None

    # Opening turn stored separately for easy retrieval
    opening_turn: Turn | None = None

    # Scenario metadata — preserved so callers can record accurate history
    # without having to reconstruct it from persona internals.
    scenario_type: str = "salary"
    difficulty: str = "medium"


@dataclass
class TurnResult:
    """
    Returned to the caller on each ``negotiate()`` call.
    Contains both the raw Turn data and convenience fields.
    """
    turn_number: int
    opponent_text: str
    opponent_offer: float | None
    resolved: bool
    agreed_value: float | None
    session_status: SessionStatus


# ---------------------------------------------------------------------------
# In-memory store (swap this layer for persistence)
# ---------------------------------------------------------------------------

MAX_ROUNDS = 20

_SESSIONS: dict[str, NegotiationSession] = {}
_sessions_lock = threading.Lock()


def _serialize_session(session: NegotiationSession) -> dict:
    """Convert a session to a JSON-serializable dict for file persistence."""
    state = session.state
    persona = state.persona
    return {
        "session_id": session.session_id,
        "status": session.status.value,
        "created_at": session.created_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "scenario_type": session.scenario_type,
        "difficulty": session.difficulty,
        "persona": {
            "name": persona.name,
            "role": persona.role,
            "style": persona.style.value,
            "pressure": persona.pressure.value,
            "target_price": persona.target_price,
            "reservation_price": persona.reservation_price,
            "opening_offer": persona.opening_offer,
            "patience": persona.patience,
            "transparency": persona.transparency,
            "emotional_reactivity": persona.emotional_reactivity,
            "hidden_constraints": persona.hidden_constraints,
            "system_prompt": persona.system_prompt,
        },
        "state": {
            "user_last_offer": state.user_last_offer,
            "opponent_last_offer": state.opponent_last_offer,
            "user_opening_anchor": state.user_opening_anchor,
            "opponent_opening_anchor": state.opponent_opening_anchor,
            "user_concession_count": state.user_concession_count,
            "opponent_concession_count": state.opponent_concession_count,
            "user_question_count": state.user_question_count,
            "user_batna_signals": state.user_batna_signals,
            "user_information_shares": state.user_information_shares,
            "user_total_concession": state.user_total_concession,
            "opponent_total_concession": state.opponent_total_concession,
            "turn_count": state.turn_count,
            "resolved": state.resolved,
            "agreed_value": state.agreed_value,
            "transcript": [
                {
                    "turn_number": t.turn_number,
                    "speaker": t.speaker.value,
                    "text": t.text,
                    "move_type": t.move_type.value,
                    "offer_amount": t.offer_amount,
                    "concession_from": t.concession_from,
                }
                for t in state.transcript
            ],
        },
    }


def _deserialize_session(data: dict) -> NegotiationSession:
    """Rebuild a NegotiationSession from a serialized dict."""
    from dealsim_mvp.core.persona import NegotiationStyle, PressureLevel

    p = data["persona"]
    persona = NegotiationPersona(
        name=p["name"],
        role=p["role"],
        style=NegotiationStyle(p["style"]),
        pressure=PressureLevel(p["pressure"]),
        target_price=p["target_price"],
        reservation_price=p["reservation_price"],
        opening_offer=p["opening_offer"],
        patience=p["patience"],
        transparency=p["transparency"],
        emotional_reactivity=p["emotional_reactivity"],
        hidden_constraints=p.get("hidden_constraints", []),
        system_prompt=p.get("system_prompt", ""),
    )

    from dealsim_mvp.core.simulator import MoveType, TurnSpeaker

    s = data["state"]
    transcript = [
        Turn(
            turn_number=t["turn_number"],
            speaker=TurnSpeaker(t["speaker"]),
            text=t["text"],
            move_type=MoveType(t["move_type"]),
            offer_amount=t.get("offer_amount"),
            concession_from=t.get("concession_from"),
        )
        for t in s.get("transcript", [])
    ]

    state = NegotiationState(
        persona=persona,
        user_last_offer=s.get("user_last_offer"),
        opponent_last_offer=s.get("opponent_last_offer"),
        user_opening_anchor=s.get("user_opening_anchor"),
        opponent_opening_anchor=s.get("opponent_opening_anchor"),
        user_concession_count=s.get("user_concession_count", 0),
        opponent_concession_count=s.get("opponent_concession_count", 0),
        user_question_count=s.get("user_question_count", 0),
        user_batna_signals=s.get("user_batna_signals", 0),
        user_information_shares=s.get("user_information_shares", 0),
        user_total_concession=s.get("user_total_concession", 0.0),
        opponent_total_concession=s.get("opponent_total_concession", 0.0),
        turn_count=s.get("turn_count", 0),
        resolved=s.get("resolved", False),
        agreed_value=s.get("agreed_value"),
        transcript=transcript,
    )

    sim = RuleBasedSimulator()

    created_at = datetime.fromisoformat(data["created_at"])
    completed_at = (
        datetime.fromisoformat(data["completed_at"])
        if data.get("completed_at")
        else None
    )

    return NegotiationSession(
        session_id=data["session_id"],
        persona=persona,
        state=state,
        simulator=sim,
        status=SessionStatus(data.get("status", "active")),
        created_at=created_at,
        completed_at=completed_at,
        scenario_type=data.get("scenario_type", "salary"),
        difficulty=data.get("difficulty", "medium"),
    )


def _persist_one(session: NegotiationSession) -> None:
    """Save a single session to its own file on disk.

    Caller must already hold _sessions_lock.
    Writes only the one file that changed — O(1) regardless of active
    session count. os.replace() inside save_session() makes it atomic.
    """
    try:
        save_session(session.session_id, _serialize_session(session))
    except Exception:
        logger.debug("Failed to persist session %s to file", session.session_id, exc_info=True)


def _restore_from_file() -> None:
    """Load all session files into memory (called once at import)."""
    with _sessions_lock:
        try:
            data = load_all_sessions()
            for sid, sdata in data.items():
                if sid not in _SESSIONS:
                    _SESSIONS[sid] = _deserialize_session(sdata)
            if data:
                logger.info("Restored %d sessions from file store", len(data))
        except Exception:
            logger.debug("Failed to restore sessions from file", exc_info=True)


# Restore on module load
_restore_from_file()


def _store_session(session: NegotiationSession) -> None:
    """Store session in memory and persist only this session to disk."""
    with _sessions_lock:
        _SESSIONS[session.session_id] = session
        _persist_one(session)


def _load_session(session_id: str) -> NegotiationSession:
    """Load session from memory, falling back to disk if not present.

    The disk fallback handles multi-worker deployments: if Worker B
    receives a request for a session that Worker A created, Worker B's
    in-memory dict won't have it, but the file will be there.
    """
    with _sessions_lock:
        session = _SESSIONS.get(session_id)
        if session is None:
            # Disk fallback — handles multi-worker case
            try:
                sdata = load_session(session_id)
                session = _deserialize_session(sdata)
                _SESSIONS[session_id] = session
                logger.debug("Loaded session %s from disk (multi-worker fallback)", session_id)
            except (FileNotFoundError, ValueError):
                raise KeyError(f"Session not found: {session_id}")
    return session


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_session(
    scenario: dict | None = None,
    persona: NegotiationPersona | None = None,
    simulator: SimulatorBase | None = None,
) -> tuple[str, Turn]:
    """
    Create a new negotiation session.

    Parameters
    ----------
    scenario:
        Dict passed to ``generate_persona_for_scenario`` if ``persona`` is None.
        Keys: ``type`` (str), ``target_value`` (float), ``difficulty`` (str).
    persona:
        Pre-built persona — takes precedence over ``scenario`` if provided.
    simulator:
        Simulator instance to use.  Defaults to ``RuleBasedSimulator()``.
        Swap this argument to use an LLM-backed engine.

    Returns
    -------
    (session_id, opening_turn)
        The session ID for subsequent calls and the opponent's opening statement.
    """
    if persona is None:
        if scenario is None:
            scenario = {"type": "salary", "target_value": 100_000, "difficulty": "medium"}
        persona = generate_persona_for_scenario(scenario)

    sim   = simulator or RuleBasedSimulator()
    state = sim.initialize_state(persona)

    session_id   = str(uuid.uuid4())
    opening_turn = sim.opening_statement(state)

    # Extract scenario metadata for history recording; default to sensible
    # values when callers supply a pre-built persona without a scenario dict.
    _stype = scenario.get("type", "salary") if scenario else "salary"
    _diff  = scenario.get("difficulty", "medium") if scenario else "medium"

    session = NegotiationSession(
        session_id=session_id,
        persona=persona,
        state=state,
        simulator=sim,
        opening_turn=opening_turn,
        scenario_type=_stype,
        difficulty=_diff,
    )
    _store_session(session)
    return session_id, opening_turn


async def create_session_async(
    scenario: dict | None = None,
    persona: NegotiationPersona | None = None,
    simulator: SimulatorBase | None = None,
) -> tuple[str, Turn]:
    """Async variant of create_session.

    When the simulator is an LLMSimulator, awaits the async opening_statement
    to avoid the ``asyncio.run()`` inside-running-loop crash.  For any other
    simulator (or when LLMSimulator is unavailable), delegates to the sync
    ``create_session`` which works identically.
    """
    if persona is None:
        if scenario is None:
            scenario = {"type": "salary", "target_value": 100_000, "difficulty": "medium"}
        persona = generate_persona_for_scenario(scenario)

    sim = simulator or RuleBasedSimulator()
    state = sim.initialize_state(persona)

    session_id = str(uuid.uuid4())

    # Use async opening if available
    if _LLMSimulator is not None and isinstance(sim, _LLMSimulator):
        opening_turn = await sim.opening_statement_async(state)
    else:
        opening_turn = sim.opening_statement(state)

    _stype = scenario.get("type", "salary") if scenario else "salary"
    _diff  = scenario.get("difficulty", "medium") if scenario else "medium"

    session = NegotiationSession(
        session_id=session_id,
        persona=persona,
        state=state,
        simulator=sim,
        opening_turn=opening_turn,
        scenario_type=_stype,
        difficulty=_diff,
    )
    _store_session(session)
    return session_id, opening_turn


async def negotiate_async(session_id: str, user_message: str) -> TurnResult:
    """Async variant of negotiate.

    When the session's simulator is an LLMSimulator, awaits the async
    generate_response to avoid the ``asyncio.run()`` crash inside FastAPI.
    """
    session = _load_session(session_id)

    if session.status != SessionStatus.ACTIVE:
        raise RuntimeError(
            f"Session {session_id} is {session.status.value} — cannot accept new turns."
        )

    # Use async generate if available
    if _LLMSimulator is not None and isinstance(session.simulator, _LLMSimulator):
        opp_turn = await session.simulator.generate_response_async(session.state, user_message)
    else:
        opp_turn = session.simulator.generate_response(session.state, user_message)

    # Auto-complete after MAX_ROUNDS
    if session.state.turn_count >= MAX_ROUNDS and not session.state.resolved:
        session.state.resolved = True
        if session.state.agreed_value is None:
            user_last = session.state.user_last_offer
            opp_last = session.state.opponent_last_offer
            if user_last is not None and opp_last is not None:
                session.state.agreed_value = (user_last + opp_last) / 2
            elif opp_last is not None:
                session.state.agreed_value = opp_last
            elif user_last is not None:
                session.state.agreed_value = user_last

    if session.state.resolved:
        session.status      = SessionStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc)

    _store_session(session)

    return TurnResult(
        turn_number=opp_turn.turn_number,
        opponent_text=opp_turn.text,
        opponent_offer=opp_turn.offer_amount,
        resolved=session.state.resolved,
        agreed_value=session.state.agreed_value,
        session_status=session.status,
    )


def negotiate(session_id: str, user_message: str) -> TurnResult:
    """
    Submit one user message and receive the opponent's response.

    Raises
    ------
    KeyError
        If ``session_id`` is unknown.
    RuntimeError
        If the session is not in ACTIVE status.

    Concurrency note (single-server / single-worker)
    -------------------------------------------------
    The load → mutate → store cycle is NOT atomic across concurrent requests
    for the same session.  For the MVP (one uvicorn worker), this is safe
    because asyncio is cooperative: there is no context switch between
    _load_session() and _store_session() unless we hit an ``await`` (we
    don't here — generate_response is synchronous).

    Multi-worker fix path: replace _SESSIONS with a Redis hash and wrap
    the entire load/modify/store in a WATCH + MULTI/EXEC transaction, or
    use a per-session distributed lock.  See store.py for the per-session
    file layer that makes the disk side already worker-safe.
    """
    session = _load_session(session_id)

    if session.status != SessionStatus.ACTIVE:
        raise RuntimeError(
            f"Session {session_id} is {session.status.value} — cannot accept new turns."
        )

    opp_turn = session.simulator.generate_response(session.state, user_message)

    # Auto-complete after MAX_ROUNDS
    if session.state.turn_count >= MAX_ROUNDS and not session.state.resolved:
        session.state.resolved = True
        # Set agreed_value so the scorecard has a meaningful outcome:
        # use midpoint of last offers if both exist, else last opponent offer.
        if session.state.agreed_value is None:
            user_last = session.state.user_last_offer
            opp_last = session.state.opponent_last_offer
            if user_last is not None and opp_last is not None:
                session.state.agreed_value = (user_last + opp_last) / 2
            elif opp_last is not None:
                session.state.agreed_value = opp_last
            elif user_last is not None:
                session.state.agreed_value = user_last

    if session.state.resolved:
        session.status      = SessionStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc)

    _store_session(session)

    return TurnResult(
        turn_number=opp_turn.turn_number,
        opponent_text=opp_turn.text,
        opponent_offer=opp_turn.offer_amount,
        resolved=session.state.resolved,
        agreed_value=session.state.agreed_value,
        session_status=session.status,
    )


def complete_session(session_id: str) -> Scorecard:
    """
    Force-complete a session (e.g. user gives up or time runs out) and
    generate the scorecard.

    Safe to call on an already-completed session — returns cached scorecard.
    """
    session = _load_session(session_id)

    if session.scorecard is not None:
        return session.scorecard

    if session.status == SessionStatus.ACTIVE:
        session.status       = SessionStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc)

    scorecard          = generate_scorecard(session.state, session_id)
    session.scorecard  = scorecard
    _store_session(session)
    return scorecard


def get_transcript(session_id: str) -> list[Turn]:
    """Return the full ordered transcript for a session."""
    return _load_session(session_id).state.transcript


def get_session_state(session_id: str) -> NegotiationState:
    """Return the raw NegotiationState (for advanced callers / debugging)."""
    return _load_session(session_id).state


def get_session_status(session_id: str) -> SessionStatus:
    """Return the session's lifecycle status (ACTIVE, COMPLETED, etc.)."""
    return _load_session(session_id).status


def get_session_meta(session_id: str) -> dict:
    """Return lightweight session metadata (scenario_type, difficulty).

    Used by API layer to record accurate user history without having to
    reconstruct scenario context from persona internals.

    Returns
    -------
    dict with keys: scenario_type (str), difficulty (str)
    """
    session = _load_session(session_id)
    return {
        "scenario_type": session.scenario_type,
        "difficulty": session.difficulty,
    }


def list_sessions() -> list[dict]:
    """Return lightweight metadata for all sessions (no transcript data)."""
    with _sessions_lock:
        return [
            {
                "session_id": s.session_id,
                "persona": s.persona.name,
                "status": s.status.value,
                "turns": s.state.turn_count,
                "resolved": s.state.resolved,
                "agreed_value": s.state.agreed_value,
                "created_at": s.created_at.isoformat(),
            }
            for s in _SESSIONS.values()
        ]
