"""Thin service layer over the compiled hub graph.

Turns a user message + thread id into a structured response (reply text, route,
confidence, rationale, per-turn trace, and the route-specific payload). This is
what the HTTP API and any UI consume.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage

from .hub import get_app


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _shape_response(state: dict) -> dict:
    route = state.get("route")
    messages = state.get("messages") or []
    reply = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            reply = msg.content
            break

    response: dict[str, Any] = {
        "reply": reply,
        "route": route,
        "confidence": state.get("confidence"),
        "rationale": state.get("routing_rationale"),
        "trace": state.get("trace") or [],
        "workout": None,
        "log_entries": [],
    }
    # Only surface the payload that belongs to the current turn's route.
    if route == "WORKOUT_GENERATE":
        response["workout"] = state.get("workout")
    elif route == "WORKOUT_LOG":
        response["log_entries"] = state.get("log_entries") or []
    return response


def run_turn(message: str, thread_id: str) -> dict:
    app = get_app()
    state = app.invoke(
        {"messages": [HumanMessage(content=message)]},
        config=_config(thread_id),
    )
    return _shape_response(state)


async def stream_turn(message: str, thread_id: str) -> AsyncIterator[dict]:
    """Stream node-level updates as they happen (stretch goal: streaming)."""
    app = get_app()
    async for chunk in app.astream(
        {"messages": [HumanMessage(content=message)]},
        config=_config(thread_id),
        stream_mode="updates",
    ):
        for node_name, update in chunk.items():
            yield {"node": node_name, "update": _jsonify(update)}
    # Final consolidated state for the client to render the full turn.
    final = app.get_state(_config(thread_id)).values
    yield {"node": "__final__", "update": _shape_response(final)}


def session_logs(thread_id: str) -> list[dict]:
    """All matched WORKOUT_LOG entries currently in the thread's state."""
    app = get_app()
    snapshot = app.get_state(_config(thread_id))
    if not snapshot or not snapshot.values:
        return []
    return snapshot.values.get("log_entries") or []


def _jsonify(update: Any) -> Any:
    """Make a node update JSON-serialisable (drop raw message objects)."""
    if not isinstance(update, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, value in update.items():
        if key == "messages":
            safe["messages"] = [
                getattr(m, "content", str(m)) for m in value if getattr(m, "content", None)
            ]
        else:
            safe[key] = value
    return safe
