"""
Pydantic request and response models for the DealSim API.

Kept in a separate file so routes.py stays readable and models can be
imported by tests without pulling in FastAPI routing machinery.

NOTE: The canonical models used at runtime are defined inline in routes.py.
This file mirrors them for documentation and test import purposes.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


# ------------------------------------------------------------------ #
# Request models
# ------------------------------------------------------------------ #

class CreateSessionRequest(BaseModel):
    scenario_type: str = Field(
        default="salary",
        examples=["salary", "freelance", "business", "custom"],
        description="Type of negotiation scenario.",
    )
    target_value: float = Field(
        gt=0,
        description="The user's goal value — e.g. desired salary or hourly rate.",
        examples=[120000, 150],
    )
    difficulty: str = Field(
        default="medium",
        examples=["easy", "medium", "hard"],
        description="Controls opponent patience, transparency, and budget constraints.",
    )
    context: str = Field(
        default="",
        max_length=500,
        description="Optional free-text context (role, company, situation).",
    )

    @field_validator("target_value")
    @classmethod
    def target_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("target_value must be positive")
        return v


class SendMessageRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=2000,
        description="The user's negotiation message.",
    )


# ------------------------------------------------------------------ #
# Response models (mirror routes.py inline models)
# ------------------------------------------------------------------ #

class CreateSessionResponse(BaseModel):
    session_id: str
    opponent_name: str
    opponent_role: str
    opening_message: str
    opening_offer: float | None = None


class SendMessageResponse(BaseModel):
    opponent_response: str
    opponent_offer: float | None = None
    round_number: int
    resolved: bool
    agreed_value: float | None = None
    session_status: str


class DimensionItem(BaseModel):
    name: str
    score: int
    weight: float
    explanation: str
    tips: list[str]


class CompleteResponse(BaseModel):
    overall_score: int
    dimensions: list[DimensionItem]
    top_tips: list[str]
    outcome: str
    agreed_value: float | None = None
    opponent_name: str


class SessionStateResponse(BaseModel):
    session_id: str
    status: str
    round_number: int
    transcript: list[dict]


class HealthResponse(BaseModel):
    status: str
    version: str
