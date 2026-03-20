"""
FastAPI router for the DealSim negotiation API.

Endpoints:
  Sessions:     POST /sessions, POST /sessions/{id}/message,
                POST /sessions/{id}/complete, GET /sessions/{id}
  Debrief:      GET /sessions/{id}/debrief, GET /sessions/{id}/playbook
  Offers:       POST /offers/analyze, GET /market-data/{role}/{location}
  Users:        GET /users/{id}/history, GET /users/{id}/patterns
  Challenges:   GET /challenges/today, POST /challenges/today/submit
  Feedback:     POST /feedback, POST /events
  Utility:      GET /scenarios, POST /tools/earnings-calculator,
                POST /tools/audit-email

Every endpoint auto-tracks its feature category via the AnalyticsTracker.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field, field_validator

# Session ID format validation (UUID4)
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Allowed values for validated enum-like fields
_ALLOWED_SCENARIO_TYPES = frozenset({
    "salary", "freelance", "rent", "medical_bill",
    "car_buying", "scope_creep", "raise", "vendor",
    "counter_offer", "budget_request",
})
_ALLOWED_DIFFICULTIES = frozenset({"easy", "medium", "hard"})

# User ID format validation (alphanumeric, underscore, hyphen; max 64 chars)
USER_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

# Maximum raw request body size for mutation endpoints (bytes)
_MAX_BODY_BYTES = 64 * 1024  # 64 KB


def validate_user_id(user_id: str) -> str:
    """Validate user_id to prevent path traversal attacks."""
    if not USER_ID_PATTERN.match(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    return user_id


def _dict_depth(d, current=0):
    """Calculate max nesting depth of a dict."""
    if not isinstance(d, dict) or not d:
        return current
    return max(_dict_depth(v, current + 1) for v in d.values())


def _api_error(status_code: int, message: str, code: str, request_id: str | None = None) -> HTTPException:
    """Return an HTTPException with the standard error shape.

    Response body: {"error": "<message>", "code": "<ERROR_CODE>", "request_id": "<uuid>"}
    """
    detail: dict = {"error": message, "code": code}
    if request_id:
        detail["request_id"] = request_id
    return HTTPException(status_code=status_code, detail=detail)


def _validate_session_id(session_id: str, request_id: str | None = None) -> str:
    """Validate that session_id is a proper UUID4 format."""
    if not _UUID4_RE.match(session_id):
        raise _api_error(400, "Invalid session ID format", "INVALID_SESSION_ID", request_id)
    return session_id

from dealsim_mvp.core.session import (
    SessionStatus,
    complete_session,
    create_session,
    get_session_meta,
    get_session_state,
    get_session_status,
    get_transcript,
    negotiate,
)
from dealsim_mvp.core.scorer import generate_scorecard
from dealsim_mvp.analytics import get_tracker
from dealsim_mvp.feedback import get_collector
from dealsim_mvp.api.debrief import generate_debrief, generate_playbook
from dealsim_mvp.api.offer_analyzer import (
    analyze_offer,
    audit_email,
    calculate_earnings_impact,
    get_available_locations,
    get_available_roles,
    get_market_data,
)
from dealsim_mvp.api.analytics import (
    get_todays_challenge,
    get_user_history,
    get_user_patterns,
    record_session_for_user,
    submit_challenge_response,
    SessionSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# -- Safe tracking helpers (never let analytics break the API) ---------------

def _track(event_type: str, data: dict | None = None) -> None:
    try:
        get_tracker().track(event_type, data)
    except Exception:
        pass


def _feature(feature_name: str, extra: dict | None = None) -> None:
    try:
        get_tracker().track_feature(feature_name, extra)
    except Exception:
        pass


# =========================================================================
# Request / Response Models
# =========================================================================

# -- Sessions -------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    scenario_type: str = Field(default="salary", examples=["salary", "freelance"])
    target_value: float = Field(gt=0, examples=[120000])
    difficulty: str = Field(default="medium", examples=["easy", "medium", "hard"])
    context: str = Field(default="", max_length=500, examples=["Senior engineer role at a startup"])
    custom_context: str | None = Field(default=None, max_length=500, description="User-supplied situational context injected into the opponent persona")
    user_id: str = Field(default="", max_length=128, description="Optional user ID for history tracking")
    opponent_params: dict | None = Field(default=None, description="Slider overrides for opponent persona tuning")

    @field_validator("scenario_type")
    @classmethod
    def scenario_type_must_be_allowed(cls, v: str) -> str:
        if v not in _ALLOWED_SCENARIO_TYPES:
            raise ValueError(
                f"scenario_type must be one of: {sorted(_ALLOWED_SCENARIO_TYPES)}"
            )
        return v

    @field_validator("difficulty")
    @classmethod
    def difficulty_must_be_allowed(cls, v: str) -> str:
        if v not in _ALLOWED_DIFFICULTIES:
            raise ValueError("difficulty must be one of: easy, medium, hard")
        return v


class CreateSessionResponse(BaseModel):
    session_id: str
    opponent_name: str
    opponent_role: str
    opening_message: str
    opening_offer: float | None = None


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000, examples=["I was thinking around $135,000"])


class SendMessageResponse(BaseModel):
    opponent_response: str
    opponent_offer: float | None = None
    round_number: int
    resolved: bool
    agreed_value: float | None = None
    session_status: str


class CompleteResponse(BaseModel):
    overall_score: int
    dimensions: list[dict]
    top_tips: list[str]
    outcome: str
    agreed_value: float | None = None
    opponent_name: str


class SessionStateResponse(BaseModel):
    session_id: str
    status: str
    round_number: int
    transcript: list[dict]


# -- Debrief & Playbook ---------------------------------------------------

class MoveAnalysisItem(BaseModel):
    turn_number: int
    speaker: str
    move_type: str
    offer: float | None = None
    analysis: str
    strength: str
    missed_opportunity: str | None = None


class DebriefResponse(BaseModel):
    session_id: str
    opponent_target: float
    opponent_reservation: float
    opponent_pressure: str
    hidden_constraints: list[str]
    agreed_value: float | None = None
    money_left_on_table: float | None = None
    optimal_outcome: float
    outcome_grade: str
    move_analysis: list[MoveAnalysisItem]
    key_moments: list[str]
    biggest_mistake: str | None = None
    best_move: str | None = None


class PlaybookEntryItem(BaseModel):
    category: str
    title: str
    description: str
    priority: str


class PlaybookResponse(BaseModel):
    session_id: str
    overall_score: int
    style_profile: str
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[PlaybookEntryItem]
    practice_scenarios: list[str]


# -- Offer Analysis -------------------------------------------------------

class OfferAnalyzeRequest(BaseModel):
    offer_text: str = Field(
        min_length=5,
        max_length=5000,
        examples=["Base salary $130k, 15% annual bonus, 10k signing bonus, 4 weeks PTO"],
    )
    role: str = Field(default="", examples=["software_engineer"])
    location: str = Field(default="", examples=["san_francisco"])


class OfferComponentItem(BaseModel):
    name: str
    value: str
    numeric_value: float | None = None
    negotiability: str
    market_position: str | None = None
    notes: str = ""


class CounterStrategyItem(BaseModel):
    name: str
    description: str
    suggested_counter: str
    risk_level: str
    rationale: str


class OfferAnalyzeResponse(BaseModel):
    components: list[OfferComponentItem]
    overall_market_position: str
    overall_score: int
    counter_strategies: list[CounterStrategyItem]
    key_insights: list[str]


class MarketDataResponse(BaseModel):
    role: str
    location: str
    p25: float
    p50: float
    p75: float
    p90: float
    source: str


# -- User Progress --------------------------------------------------------

class UserHistoryResponse(BaseModel):
    user_id: str
    total_sessions: int
    sessions: list[dict]
    average_score: float
    best_score: int
    worst_score: int
    score_trend: str
    favorite_scenario: str | None = None


class PatternItem(BaseModel):
    name: str
    description: str
    frequency: str
    impact: str
    recommendation: str


class UserPatternsResponse(BaseModel):
    user_id: str
    sessions_analyzed: int
    patterns: list[PatternItem]
    style_profile: str
    top_strength: str | None = None
    top_weakness: str | None = None


# -- Daily Challenges -----------------------------------------------------

class ChallengeResponse(BaseModel):
    id: str
    title: str
    description: str
    scenario_prompt: str
    scoring_criteria: list[str]
    max_score: int
    category: str
    date: str


class ChallengeSubmitRequest(BaseModel):
    user_id: str = Field(default="anonymous")
    response: str = Field(min_length=5, max_length=5000)


class CriterionBreakdown(BaseModel):
    criterion: str
    met: bool
    score: int
    max: int


class ChallengeSubmitResponse(BaseModel):
    total: int
    breakdown: list[CriterionBreakdown]
    challenge: dict


# -- Feedback & Events ----------------------------------------------------

class FeedbackRequest(BaseModel):
    session_id: str = Field(..., description="Session that generated the feedback")
    rating: int = Field(..., ge=1, le=5, description="1-5 star rating")
    comment: str = Field(default="", max_length=1000)
    email: str = Field(default="", max_length=200)
    final_score: int | None = Field(default=None)
    scenario_type: str | None = Field(default=None)


class EventRequest(BaseModel):
    event_type: str = Field(..., max_length=50)
    properties: dict = Field(default_factory=dict)

    @field_validator('properties')
    @classmethod
    def validate_properties(cls, v):
        """Prevent memory exhaustion from oversized event properties."""
        import json
        serialized = json.dumps(v)
        if len(serialized) > 4096:
            raise ValueError('properties payload too large (max 4KB)')
        if _dict_depth(v) > 3:
            raise ValueError('properties nested too deeply (max depth 3)')
        return v


# -- Tools ----------------------------------------------------------------

class EarningsCalcRequest(BaseModel):
    current_offer: float = Field(gt=0, examples=[110000])
    negotiated_offer: float = Field(gt=0, examples=[125000])


class EarningsCalcResponse(BaseModel):
    current_offer: float
    negotiated_offer: float
    difference_annual: float
    difference_5yr: float
    difference_10yr: float
    difference_career: float
    compounding_note: str


class AuditEmailRequest(BaseModel):
    email_text: str = Field(min_length=10, max_length=10000)


class AuditEmailResponse(BaseModel):
    overall_score: int
    tone: str
    strengths: list[str]
    issues: list[str]
    suggestions: list[str]
    rewrite_hints: list[str]


class ScenarioItem(BaseModel):
    type: str
    name: str
    description: str
    default_target: float
    difficulties: list[str]


# =========================================================================
# Session Endpoints
# =========================================================================

@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new negotiation",
    tags=["sessions"],
)
async def api_create_session(request: Request, body: CreateSessionRequest) -> CreateSessionResponse:
    req_id = request.state.request_id
    content_length = int(request.headers.get("content-length", 0))
    if content_length > _MAX_BODY_BYTES:
        raise _api_error(413, "Request body too large", "BODY_TOO_LARGE", req_id)

    scenario = {
        "type": body.scenario_type,
        "target_value": body.target_value,
        "difficulty": body.difficulty,
        "context": body.context,
        "custom_context": body.custom_context,
        "opponent_params": body.opponent_params,
    }
    try:
        sid, opening_turn = create_session(scenario=scenario)
    except Exception as exc:
        logger.exception("Failed to create session [request_id=%s]", req_id)
        raise _api_error(500, "Internal server error", "INTERNAL_ERROR", req_id) from exc

    _track("session_created", {
        "session_id": sid,
        "scenario_type": body.scenario_type,
        "difficulty": body.difficulty,
        "user_id": body.user_id or None,
    })
    _feature("simulation", {"scenario_type": body.scenario_type})

    state = get_session_state(sid)
    return CreateSessionResponse(
        session_id=sid,
        opponent_name=state.persona.name,
        opponent_role=state.persona.role,
        opening_message=opening_turn.text,
        opening_offer=opening_turn.offer_amount,
    )


@router.post(
    "/sessions/{session_id}/message",
    response_model=SendMessageResponse,
    summary="Send a message in the negotiation",
    tags=["sessions"],
)
async def api_send_message(request: Request, session_id: str, body: SendMessageRequest) -> SendMessageResponse:
    req_id = request.state.request_id
    content_length = int(request.headers.get("content-length", 0))
    if content_length > _MAX_BODY_BYTES:
        raise _api_error(413, "Request body too large", "BODY_TOO_LARGE", req_id)

    _validate_session_id(session_id, req_id)
    try:
        result = negotiate(session_id, body.message)
    except KeyError:
        raise _api_error(404, f"Session not found", "SESSION_NOT_FOUND", req_id)
    except (ValueError, RuntimeError) as exc:
        raise _api_error(409, "Session is not in a negotiable state", "SESSION_CONFLICT", req_id)

    _track("message_sent", {"session_id": session_id, "round_number": result.turn_number})
    _feature("simulation")

    return SendMessageResponse(
        opponent_response=result.opponent_text,
        opponent_offer=result.opponent_offer,
        round_number=result.turn_number,
        resolved=result.resolved,
        agreed_value=result.agreed_value,
        session_status=result.session_status.value,
    )


@router.post(
    "/sessions/{session_id}/complete",
    response_model=CompleteResponse,
    summary="End negotiation and get scorecard",
    tags=["sessions"],
)
async def api_complete_session(
    request: Request,
    session_id: str,
    user_id: str = Query(default="", description="Optional user ID for history tracking"),
) -> CompleteResponse:
    req_id = request.state.request_id
    _validate_session_id(session_id, req_id)
    try:
        scorecard = complete_session(session_id)
    except KeyError:
        raise _api_error(404, "Session not found", "SESSION_NOT_FOUND", req_id)

    _track("simulation_completed", {
        "session_id": session_id,
        "overall_score": scorecard.overall,
        "outcome": scorecard.outcome,
    })
    _feature("debrief", {"score": scorecard.overall})

    # Record for user history if user_id provided
    if user_id:
        try:
            meta = get_session_meta(session_id)
            record_session_for_user(SessionSummary(
                session_id=session_id,
                user_id=user_id,
                scenario_type=meta["scenario_type"],
                difficulty=meta["difficulty"],
                overall_score=scorecard.overall,
                outcome=scorecard.outcome,
                agreed_value=scorecard.agreed_value,
                opponent_name=scorecard.persona_name,
                completed_at=datetime.now(timezone.utc).isoformat(),
                dimension_scores={d.name: d.score for d in scorecard.dimensions},
            ))
        except Exception:
            logger.warning("Failed to record session for user history", exc_info=True)

    return CompleteResponse(
        overall_score=scorecard.overall,
        dimensions=[
            {
                "name": d.name,
                "score": d.score,
                "weight": d.weight,
                "explanation": d.explanation,
                "tips": d.tips,
            }
            for d in scorecard.dimensions
        ],
        top_tips=scorecard.top_tips,
        outcome=scorecard.outcome,
        agreed_value=scorecard.agreed_value,
        opponent_name=scorecard.persona_name,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=SessionStateResponse,
    summary="Get session state",
    tags=["sessions"],
)
def api_get_session(request: Request, session_id: str) -> SessionStateResponse:
    req_id = request.state.request_id
    _validate_session_id(session_id, req_id)
    try:
        state = get_session_state(session_id)
        session_status = get_session_status(session_id)
        transcript = get_transcript(session_id)
    except KeyError:
        raise _api_error(404, "Session not found", "SESSION_NOT_FOUND", req_id)

    return SessionStateResponse(
        session_id=session_id,
        status=session_status.value,
        round_number=state.turn_count,
        transcript=[
            {"speaker": t.speaker.value, "text": t.text, "offer": t.offer_amount}
            for t in transcript
        ],
    )


# =========================================================================
# Debrief & Playbook Endpoints
# =========================================================================

@router.get(
    "/sessions/{session_id}/debrief",
    response_model=DebriefResponse,
    summary="Get post-negotiation debrief with hidden state and move analysis",
    tags=["debrief"],
)
def api_get_debrief(request: Request, session_id: str) -> DebriefResponse:
    req_id = request.state.request_id
    _validate_session_id(session_id, req_id)
    try:
        session_status = get_session_status(session_id)
    except KeyError:
        raise _api_error(404, "Session not found", "SESSION_NOT_FOUND", req_id)

    if session_status == SessionStatus.ACTIVE:
        raise _api_error(
            409,
            "Session is still active. Complete the negotiation before viewing the debrief.",
            "SESSION_STILL_ACTIVE",
            req_id,
        )

    state = get_session_state(session_id)

    _track("debrief_viewed", {"session_id": session_id})
    _feature("debrief")

    debrief = generate_debrief(state, session_id)

    return DebriefResponse(
        session_id=debrief.session_id,
        opponent_target=debrief.opponent_target,
        opponent_reservation=debrief.opponent_reservation,
        opponent_pressure=debrief.opponent_pressure,
        hidden_constraints=debrief.hidden_constraints,
        agreed_value=debrief.agreed_value,
        money_left_on_table=debrief.money_left_on_table,
        optimal_outcome=debrief.optimal_outcome,
        outcome_grade=debrief.outcome_grade,
        move_analysis=[
            MoveAnalysisItem(
                turn_number=m.turn_number,
                speaker=m.speaker,
                move_type=m.move_type,
                offer=m.offer,
                analysis=m.analysis,
                strength=m.strength,
                missed_opportunity=m.missed_opportunity,
            )
            for m in debrief.move_analysis
        ],
        key_moments=debrief.key_moments,
        biggest_mistake=debrief.biggest_mistake,
        best_move=debrief.best_move,
    )


@router.get(
    "/sessions/{session_id}/playbook",
    response_model=PlaybookResponse,
    summary="Get personalized negotiation playbook based on session performance",
    tags=["debrief"],
)
def api_get_playbook(request: Request, session_id: str) -> PlaybookResponse:
    req_id = request.state.request_id
    _validate_session_id(session_id, req_id)
    try:
        state = get_session_state(session_id)
    except KeyError:
        raise _api_error(404, "Session not found", "SESSION_NOT_FOUND", req_id)

    # Generate scorecard from current state without completing the session
    scorecard = generate_scorecard(state, session_id)

    _track("playbook_generated", {"session_id": session_id})
    _feature("playbook")

    playbook = generate_playbook(state, session_id, scorecard.overall)

    return PlaybookResponse(
        session_id=playbook.session_id,
        overall_score=playbook.overall_score,
        style_profile=playbook.style_profile,
        strengths=playbook.strengths,
        weaknesses=playbook.weaknesses,
        recommendations=[
            PlaybookEntryItem(
                category=r.category,
                title=r.title,
                description=r.description,
                priority=r.priority,
            )
            for r in playbook.recommendations
        ],
        practice_scenarios=playbook.practice_scenarios,
    )


# =========================================================================
# Offer Analysis Endpoints
# =========================================================================

@router.post(
    "/offers/analyze",
    response_model=OfferAnalyzeResponse,
    summary="Analyze a job offer for market position, negotiability, and counter strategies",
    tags=["offers"],
)
async def api_analyze_offer(request: Request, body: OfferAnalyzeRequest) -> OfferAnalyzeResponse:
    req_id = request.state.request_id
    content_length = int(request.headers.get("content-length", 0))
    if content_length > _MAX_BODY_BYTES:
        raise _api_error(413, "Request body too large", "BODY_TOO_LARGE", req_id)
    _track("offer_analyzed", {"has_role": bool(body.role), "has_location": bool(body.location)})
    _feature("offer_analyzer")

    analysis = analyze_offer(body.offer_text)

    # Enrich with market data if role/location provided
    if body.role and body.location:
        mdata = get_market_data(body.role, body.location)
        if mdata:
            for comp in analysis.components:
                if comp.name in ("base_salary", "salary", "base") and comp.numeric_value:
                    if comp.numeric_value >= mdata.p75:
                        comp.market_position = "above"
                    elif comp.numeric_value >= mdata.p50:
                        comp.market_position = "at"
                    else:
                        comp.market_position = "below"

    return OfferAnalyzeResponse(
        components=[
            OfferComponentItem(
                name=c.name, value=c.value, numeric_value=c.numeric_value,
                negotiability=c.negotiability, market_position=c.market_position,
                notes=c.notes,
            )
            for c in analysis.components
        ],
        overall_market_position=analysis.overall_market_position,
        overall_score=analysis.overall_score,
        counter_strategies=[
            CounterStrategyItem(
                name=s.name, description=s.description,
                suggested_counter=s.suggested_counter,
                risk_level=s.risk_level, rationale=s.rationale,
            )
            for s in analysis.counter_strategies
        ],
        key_insights=analysis.key_insights,
    )


@router.get(
    "/market-data/{role}/{location}",
    response_model=MarketDataResponse,
    summary="Get salary benchmarks from bundled BLS/H1B data",
    tags=["offers"],
)
def api_get_market_data(role: str, location: str) -> MarketDataResponse:
    data = get_market_data(role, location)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="No market data found for the specified role and location.",
        )
    return MarketDataResponse(
        role=data.role, location=data.location,
        p25=data.p25, p50=data.p50, p75=data.p75, p90=data.p90,
        source=data.source,
    )


# =========================================================================
# User Progress Endpoints
# =========================================================================

@router.get(
    "/users/{user_id}/history",
    response_model=UserHistoryResponse,
    summary="Get user's score history across sessions",
    tags=["users"],
)
def api_get_user_history(user_id: str) -> UserHistoryResponse:
    validate_user_id(user_id)
    history = get_user_history(user_id)
    return UserHistoryResponse(**history)


@router.get(
    "/users/{user_id}/patterns",
    response_model=UserPatternsResponse,
    summary="Get detected negotiation patterns for a user",
    tags=["users"],
)
def api_get_user_patterns(user_id: str) -> UserPatternsResponse:
    validate_user_id(user_id)
    patterns = get_user_patterns(user_id)
    return UserPatternsResponse(
        user_id=patterns["user_id"],
        sessions_analyzed=patterns["sessions_analyzed"],
        patterns=[PatternItem(**p) for p in patterns["patterns"]],
        style_profile=patterns["style_profile"],
        top_strength=patterns["top_strength"],
        top_weakness=patterns["top_weakness"],
    )


# =========================================================================
# Daily Challenge Endpoints
# =========================================================================

@router.get(
    "/challenges/today",
    response_model=ChallengeResponse,
    summary="Get today's daily negotiation micro-challenge",
    tags=["challenges"],
)
def api_get_todays_challenge() -> ChallengeResponse:
    c = get_todays_challenge()
    return ChallengeResponse(
        id=c["id"], title=c["title"], description=c["description"],
        scenario_prompt=c["scenario_prompt"], scoring_criteria=c["scoring_criteria"],
        max_score=c["max_score"], category=c["category"], date=c["date"],
    )


@router.post(
    "/challenges/today/submit",
    response_model=ChallengeSubmitResponse,
    summary="Submit a response to today's challenge and get a score",
    tags=["challenges"],
)
async def api_submit_challenge(request: Request, body: ChallengeSubmitRequest) -> ChallengeSubmitResponse:
    req_id = request.state.request_id
    content_length = int(request.headers.get("content-length", 0))
    if content_length > _MAX_BODY_BYTES:
        raise _api_error(413, "Request body too large", "BODY_TOO_LARGE", req_id)
    _track("challenge_completed", {"user_id": body.user_id})
    _feature("daily_challenge")

    result = submit_challenge_response(body.user_id, body.response)
    return ChallengeSubmitResponse(
        total=result["total"],
        breakdown=[CriterionBreakdown(**b) for b in result["breakdown"]],
        challenge=result["challenge"],
    )


# =========================================================================
# Feedback & Analytics Endpoints
# =========================================================================

@router.post("/feedback", summary="Submit user feedback", tags=["feedback"])
async def api_submit_feedback(request: Request, body: FeedbackRequest):
    req_id = request.state.request_id
    content_length = int(request.headers.get("content-length", 0))
    if content_length > _MAX_BODY_BYTES:
        raise _api_error(413, "Request body too large", "BODY_TOO_LARGE", req_id)
    get_collector().submit(
        session_id=body.session_id,
        rating=body.rating,
        comment=body.comment,
        email=body.email or None,
        score=body.final_score,
        scenario_type=body.scenario_type,
    )
    _track("feedback_submitted", {
        "session_id": body.session_id,
        "rating": body.rating,
        "has_comment": bool(body.comment),
    })
    _feature("feedback")
    return {"status": "ok", "message": "Thank you for your feedback!"}


@router.post("/events", summary="Track anonymous usage event", tags=["analytics"])
async def api_track_event(request: Request, body: EventRequest):
    req_id = request.state.request_id
    content_length = int(request.headers.get("content-length", 0))
    if content_length > _MAX_BODY_BYTES:
        raise _api_error(413, "Request body too large", "BODY_TOO_LARGE", req_id)
    allowed = {
        "session_created", "simulation_completed", "score_viewed",
        "feedback_submitted", "page_view", "debrief_viewed",
        "playbook_generated", "offer_analyzed", "challenge_completed",
        "feature_used", "message_sent", "email_audited",
        "earnings_calculated",
    }
    if body.event_type not in allowed:
        raise _api_error(400, f"Unknown event type: {body.event_type}", "UNKNOWN_EVENT_TYPE", req_id)
    _track(body.event_type, body.properties)
    return {"status": "ok"}


# =========================================================================
# Utility Endpoints
# =========================================================================

SCENARIOS = [
    ScenarioItem(
        type="salary",
        name="Salary Negotiation",
        description="Negotiate your salary with a hiring manager or HR representative.",
        default_target=120000,
        difficulties=["easy", "medium", "hard"],
    ),
    ScenarioItem(
        type="freelance",
        name="Freelance Rate Negotiation",
        description="Negotiate your hourly or project rate with a potential client.",
        default_target=150,
        difficulties=["easy", "medium", "hard"],
    ),
    ScenarioItem(
        type="rent",
        name="Rent Negotiation",
        description="Negotiate a rent increase with your landlord or property manager.",
        default_target=1500,
        difficulties=["easy", "medium", "hard"],
    ),
    ScenarioItem(
        type="medical_bill",
        name="Medical Bill Negotiation",
        description="Negotiate a hospital or medical bill down from the original amount.",
        default_target=5000,
        difficulties=["easy", "medium", "hard"],
    ),
    ScenarioItem(
        type="car_buying",
        name="Car Buying",
        description="Negotiate the purchase price of a car with a dealer.",
        default_target=24000,
        difficulties=["easy", "medium", "hard"],
    ),
    ScenarioItem(
        type="scope_creep",
        name="Scope Creep",
        description="Push back on a client adding extra work without adjusting the budget.",
        default_target=10000,
        difficulties=["easy", "medium", "hard"],
    ),
    ScenarioItem(
        type="raise",
        name="Raise Request",
        description="Ask your manager for a raise and negotiate the outcome.",
        default_target=95000,
        difficulties=["easy", "medium", "hard"],
    ),
    ScenarioItem(
        type="vendor",
        name="Vendor Contract",
        description="Negotiate pricing and terms with a vendor or supplier.",
        default_target=50000,
        difficulties=["easy", "medium", "hard"],
    ),
    ScenarioItem(
        type="counter_offer",
        name="Counter Offer",
        description="Counter a job offer to negotiate better compensation.",
        default_target=110000,
        difficulties=["easy", "medium", "hard"],
    ),
    ScenarioItem(
        type="budget_request",
        name="Budget Request",
        description="Request project budget from a VP or executive.",
        default_target=75000,
        difficulties=["easy", "medium", "hard"],
    ),
]


@router.get(
    "/scenarios",
    response_model=list[ScenarioItem],
    summary="List available negotiation scenario types",
    tags=["utility"],
)
def api_list_scenarios() -> list[ScenarioItem]:
    return SCENARIOS


@router.post(
    "/tools/earnings-calculator",
    response_model=EarningsCalcResponse,
    summary="Calculate lifetime earnings impact of a negotiation outcome",
    tags=["tools"],
)
async def api_earnings_calculator(request: Request, body: EarningsCalcRequest) -> EarningsCalcResponse:
    req_id = request.state.request_id
    content_length = int(request.headers.get("content-length", 0))
    if content_length > _MAX_BODY_BYTES:
        raise _api_error(413, "Request body too large", "BODY_TOO_LARGE", req_id)
    _track("earnings_calculated", {
        "current": body.current_offer,
        "negotiated": body.negotiated_offer,
    })
    _feature("earnings_calculator")

    impact = calculate_earnings_impact(body.current_offer, body.negotiated_offer)
    return EarningsCalcResponse(
        current_offer=impact.current_offer,
        negotiated_offer=impact.negotiated_offer,
        difference_annual=impact.difference_annual,
        difference_5yr=impact.difference_5yr,
        difference_10yr=impact.difference_10yr,
        difference_career=impact.difference_career,
        compounding_note=impact.compounding_note,
    )


@router.post(
    "/tools/audit-email",
    response_model=AuditEmailResponse,
    summary="Analyze a negotiation email draft for tone and effectiveness",
    tags=["tools"],
)
async def api_audit_email(request: Request, body: AuditEmailRequest) -> AuditEmailResponse:
    req_id = request.state.request_id
    content_length = int(request.headers.get("content-length", 0))
    if content_length > _MAX_BODY_BYTES:
        raise _api_error(413, "Request body too large", "BODY_TOO_LARGE", req_id)
    _track("email_audited", {"length": len(body.email_text)})
    _feature("email_auditor")

    result = audit_email(body.email_text)
    return AuditEmailResponse(
        overall_score=result.overall_score,
        tone=result.tone,
        strengths=result.strengths,
        issues=result.issues,
        suggestions=result.suggestions,
        rewrite_hints=result.rewrite_hints,
    )
