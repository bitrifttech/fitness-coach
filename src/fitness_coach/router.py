"""LLM router: structured-output classification with an explicit confidence gate.

Routing uses ``with_structured_output`` (requirement: no regex/keywords). The
router returns a route AND a calibrated confidence + rationale. A conditional
edge then sends low-confidence turns to a clarify node rather than silently
committing to a possibly-wrong route.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from .config import get_settings
from .llm import get_chat_model
from .state import HubState

ROUTE_LITERAL = Literal["COACH", "WORKOUT_GENERATE", "WORKOUT_LOG"]


class RoutingDecision(BaseModel):
    """Structured routing output produced by the LLM."""

    route: ROUTE_LITERAL = Field(description="The single best route for this user turn.")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Calibrated certainty (0-1) in the chosen route."
    )
    rationale: str = Field(description="One concise sentence explaining the choice.")
    clarify_options: list[ROUTE_LITERAL] = Field(
        default_factory=list,
        description="If ambiguous, the 2+ plausible routes to offer the user.",
    )


_SYSTEM_PROMPT = """You are the router for a fitness coaching assistant.
Classify the user's most recent message into exactly one route:

- COACH: education / advice / "how" / "what muscles" / form / programming questions.
- WORKOUT_GENERATE: the user wants you to CREATE or REVISE a workout/session/plan.
  Includes: "build me…", "adjust it", "make it easier/harder", "swap an exercise",
  "change my session". Even if they mention doing a workout in the past, if the
  ask is to produce or modify a plan, this is WORKOUT_GENERATE — not logging.
- WORKOUT_LOG: the user is SUBMITTING a log entry with concrete performance data
  to record (exercise + sets/reps/weight, e.g. "3x10 bench at 185 lbs").
  NOT logging: vague "I did a workout", questions, or requests to adjust/modify.

Guidance:
- Use conversation history for context (e.g. follow-ups to a clarifying question).
- "Adjust", "modify", "change", "tweak" a workout → WORKOUT_GENERATE (or clarify
  if you don't know what they did). NEVER WORKOUT_LOG unless they give sets/reps/weight.
- Example: "I did a workout yesterday, can you adjust it?" → WORKOUT_GENERATE or
  low-confidence clarify (options: WORKOUT_GENERATE, COACH). NOT WORKOUT_LOG.
- Be honest about confidence. Vague inputs like "bench press" with no verb are
  genuinely ambiguous — give LOW confidence and list clarify_options.
- High confidence (>=0.8) only when intent is clear and unambiguous.
"""

_ADJUST_MARKERS = (
    "adjust",
    "modify",
    "change",
    "tweak",
    "revise",
    "update",
    "easier",
    "harder",
    "swap",
    "redo",
    "rework",
)
_LOG_DATA = re.compile(
    r"\d+\s*[x×]\s*\d+|"
    r"\b\d+\s*(reps|sets)\b|"
    r"\b(reps|sets)\s*\d+\b|"
    r"\b\d+\.?\d*\s*(lbs?|kg)\b",
    re.I,
)


def _last_user_text(state: HubState) -> str:
    for msg in reversed(state.get("messages") or []):
        if getattr(msg, "type", None) == "human":
            return str(msg.content)
        if isinstance(msg, tuple) and len(msg) >= 2 and msg[0] in ("user", "human"):
            return str(msg[1])
    return ""


def log_route_is_adjust_request(state: HubState) -> bool:
    """WORKOUT_LOG is wrong when the user asks to adjust without log data."""
    if state.get("route") != "WORKOUT_LOG":
        return False
    text = _last_user_text(state).lower()
    if not text or not any(m in text for m in _ADJUST_MARKERS):
        return False
    return _LOG_DATA.search(text) is None


def _correct_log_misroute(decision: RoutingDecision, state: HubState) -> RoutingDecision:
    """Override logger when the user wants to adjust, not record sets."""
    if not log_route_is_adjust_request({**state, "route": decision.route}):
        return decision
    options = [o for o in decision.clarify_options if o != "WORKOUT_LOG"]
    for route in ("WORKOUT_GENERATE", "COACH"):
        if route not in options:
            options.append(route)
    return decision.model_copy(
        update={
            "route": "WORKOUT_GENERATE",
            "confidence": min(decision.confidence, 0.45),
            "rationale": (
                "User asked to adjust a workout, not log sets — need details on what they did."
            ),
            "clarify_options": options[:3],
        }
    )


def router_node(state: HubState) -> dict:
    model = get_chat_model(temperature=0.0).with_structured_output(RoutingDecision)
    messages = [SystemMessage(content=_SYSTEM_PROMPT), *state["messages"]]
    decision: RoutingDecision = model.invoke(messages)
    decision = _correct_log_misroute(decision, state)

    # Router runs first on every turn, so start a fresh per-turn trace here.
    trace: list = []
    trace.append(
        {
            "kind": "route",
            "label": f"{decision.route} (confidence {decision.confidence:.2f})",
            "detail": {
                "route": decision.route,
                "confidence": decision.confidence,
                "rationale": decision.rationale,
                "clarify_options": decision.clarify_options,
            },
        }
    )
    return {
        "route": decision.route,
        "confidence": decision.confidence,
        "routing_rationale": decision.rationale,
        "clarify_options": decision.clarify_options,
        "trace": trace,
    }


def route_gate(state: HubState, config: Optional[RunnableConfig] = None) -> str:
    """Conditional-edge function: pick the next node based on confidence.

    Below the configured threshold we divert to the clarify node instead of
    committing to a route. This is the explicit "don't silently misroute" policy.
    A per-request override can be passed in ``config.configurable.confidence_threshold``
    (the UI's sidebar slider sets this); otherwise we fall back to settings.
    """
    threshold = _resolve_threshold(config)
    if log_route_is_adjust_request(state):
        return "clarify"
    if state.get("confidence", 0.0) < threshold:
        return "clarify"
    return state["route"]


def _resolve_threshold(config: Optional[RunnableConfig]) -> float:
    if config:
        override = config.get("configurable", {}).get("confidence_threshold")
        if override is not None:
            return float(override)
    return get_settings().confidence_threshold
