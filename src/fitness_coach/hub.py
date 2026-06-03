"""Hub graph: a typed StateGraph that routes to composed sub-agent graphs.

    START -> router --(confidence gate)--> { clarify | coach | generator | logger } -> END

Memory is provided by a MemorySaver checkpointer keyed on thread_id, so the
clarify-then-retry flow and multi-turn context work out of the box.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .agents.coach import build_coach_graph
from .agents.generator import build_generator_graph
from .agents.logger import build_logger_graph
from .router import (
    adjust_request_needs_clarify,
    bare_phrase_needs_clarify,
    route_gate,
    router_node,
    _last_user_text,
)
from .state import HubState

_ROUTE_LABELS = {
    "COACH": "coaching question",
    "WORKOUT_GENERATE": "workout generation",
    "WORKOUT_LOG": "workout logging",
}


def _clarify(state: HubState) -> dict:
    """Low-confidence fallback: ask the user to disambiguate instead of guessing."""
    options = state.get("clarify_options") or list(_ROUTE_LABELS.keys())
    pretty = [f"{_ROUTE_LABELS.get(o, o)}" for o in options]
    if len(pretty) >= 2:
        choices = ", ".join(pretty[:-1]) + f", or {pretty[-1]}"
    else:
        choices = pretty[0] if pretty else "something else"

    conf = state.get("confidence", 0.0)
    if adjust_request_needs_clarify(state):
        msg = (
            "Happy to adjust your workout — tell me what you did (exercises, duration, "
            "equipment, how it felt), or pick an option below."
        )
    elif bare_phrase_needs_clarify(state):
        phrase = _last_user_text(state).strip() or "that"
        msg = (
            f'"{phrase}" could mean a few different things. Did you want coaching, '
            f"a new workout, or to log a set? Pick an option below."
        )
    else:
        msg = (
            f"I want to make sure I help correctly (I'm only {conf:.0%} sure what you meant). "
            f"Did you want {choices}? Let me know and I'll take it from there."
        )
    trace = list(state.get("trace") or [])
    trace.append(
        {
            "kind": "clarify",
            "label": "low confidence — asked user to disambiguate",
            "detail": {"confidence": conf, "options": options},
        }
    )
    return {"messages": [AIMessage(content=msg)], "trace": trace}


def build_hub():
    graph = StateGraph(HubState)

    graph.add_node("router", router_node)
    graph.add_node("clarify", _clarify)
    graph.add_node("coach", build_coach_graph())
    graph.add_node("generator", build_generator_graph())
    graph.add_node("logger", build_logger_graph())

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_gate,
        {
            "clarify": "clarify",
            "COACH": "coach",
            "WORKOUT_GENERATE": "generator",
            "WORKOUT_LOG": "logger",
        },
    )
    for node in ("clarify", "coach", "generator", "logger"):
        graph.add_edge(node, END)

    return graph


@lru_cache(maxsize=1)
def get_app():
    """Compile the hub once with an in-memory checkpointer."""
    return build_hub().compile(checkpointer=MemorySaver())
