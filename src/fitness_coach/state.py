"""Typed state and domain models shared across the hub and sub-agents.

``HubState`` is the single ``TypedDict`` that flows through the LangGraph
``StateGraph``. ``messages`` carries multi-turn history (reduced with
``add_messages``); ``trace`` powers the inline "show reasoning" panel in the UI.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

Route = Literal["COACH", "WORKOUT_GENERATE", "WORKOUT_LOG", "CLARIFY"]


class TraceEvent(BaseModel):
    """A single observable step, surfaced in the UI trace panel."""

    kind: str = Field(description="event type, e.g. 'route', 'tool_call', 'recovery'")
    label: str = Field(description="short human-readable summary")
    detail: dict[str, Any] = Field(default_factory=dict)


class WorkoutItem(BaseModel):
    exercise_id: str
    name: str
    sets: int
    reps: Optional[int] = None
    duration_seconds: Optional[int] = None
    rest_seconds: int
    equipment: list[str] = Field(default_factory=list)


class WorkoutSection(BaseModel):
    name: Literal["warmup", "main", "cooldown"]
    items: list[WorkoutItem] = Field(default_factory=list)


class Workout(BaseModel):
    title: str
    duration_minutes: int
    sections: list[WorkoutSection] = Field(default_factory=list)
    notes: Optional[str] = None


class LogEntry(BaseModel):
    raw_name: str = Field(description="what the user said, e.g. 'bench press'")
    matched_id: Optional[str] = Field(None, description="canonical exercise id, if matched")
    matched_name: Optional[str] = Field(None, description="canonical exercise name")
    match_score: float = Field(0.0, description="fuzzy match confidence 0-100")
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight: Optional[float] = None
    weight_unit: Optional[str] = None


class HubState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    route: Optional[Route]
    confidence: float
    routing_rationale: str
    trace: list[dict[str, Any]]
    # Route-specific payloads (only one is populated per turn):
    workout: Optional[dict[str, Any]]
    log_entries: list[dict[str, Any]]
    clarify_options: list[str]
