"""LLM router: structured-output classification with an explicit confidence gate.

Routing uses ``with_structured_output`` (requirement: no regex/keywords). The
router returns a route AND a calibrated confidence + rationale. A conditional
edge then sends low-confidence turns to a clarify node rather than silently
committing to a possibly-wrong route.
"""

from __future__ import annotations

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
- WORKOUT_GENERATE: the user wants you to CREATE a workout/session/plan.
- WORKOUT_LOG: the user is REPORTING a workout they already did (sets/reps/weight).

Guidance:
- Use conversation history for context (e.g. follow-ups to a clarifying question).
- Be honest about confidence. Vague inputs like "bench press" with no verb, or
  "I did a workout yesterday, can you adjust it?" (log? generate? coach?) are
  genuinely ambiguous — give them LOW confidence and list clarify_options.
- High confidence (>=0.8) only when intent is clear and unambiguous.
"""


def router_node(state: HubState) -> dict:
    model = get_chat_model(temperature=0.0).with_structured_output(RoutingDecision)
    messages = [SystemMessage(content=_SYSTEM_PROMPT), *state["messages"]]
    decision: RoutingDecision = model.invoke(messages)

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
    if state.get("confidence", 0.0) < threshold:
        return "clarify"
    return state["route"]


def _resolve_threshold(config: Optional[RunnableConfig]) -> float:
    if config:
        override = config.get("configurable", {}).get("confidence_threshold")
        if override is not None:
            return float(override)
    return get_settings().confidence_threshold
