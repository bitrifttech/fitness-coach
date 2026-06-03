"""Service layer: adapt the hub graph's domain state into the UI contract.

This is the boundary between the LangGraph domain (TypedDict state, trace events,
internal workout/log dicts) and the web view's expected JSON shape (route,
confidence, threshold, trace[router|tool|recover|agent|note], content payload
per route). The graph stays UI-agnostic; all reshaping lives here.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional

from langchain_core.messages import AIMessage, HumanMessage

from . import exercises
from .config import configure_observability, get_settings
from .hub import get_app

configure_observability()


def run_turn(message: str, thread_id: str, threshold: Optional[float] = None) -> dict:
    effective_threshold = _resolve_threshold(threshold)
    app = get_app()
    state = app.invoke(
        {"messages": [HumanMessage(content=message)]},
        config=_graph_config(thread_id, effective_threshold, message),
    )
    return _shape_response(state, thread_id, effective_threshold)


async def stream_turn(message: str, thread_id: str, threshold: Optional[float] = None) -> AsyncIterator[dict]:
    effective_threshold = _resolve_threshold(threshold)
    app = get_app()
    async for chunk in app.astream(
        {"messages": [HumanMessage(content=message)]},
        config=_graph_config(thread_id, effective_threshold, message),
        stream_mode="updates",
    ):
        for node_name, update in chunk.items():
            yield {"node": node_name, "update": _jsonify(update)}
    final = app.get_state(_graph_config(thread_id, effective_threshold)).values
    yield {"node": "__final__", "update": _shape_response(final, thread_id, effective_threshold)}


def session_logs(thread_id: str) -> list[dict]:
    """All matched WORKOUT_LOG entries currently in the thread's state."""
    app = get_app()
    snapshot = app.get_state(_graph_config(thread_id, _resolve_threshold(None)))
    if not snapshot or not snapshot.values:
        return []
    return [_shape_log_entry(e) for e in (snapshot.values.get("log_history") or [])]


def _resolve_threshold(client_threshold: Optional[float]) -> float:
    if client_threshold is not None:
        return float(client_threshold)
    return get_settings().confidence_threshold


def _graph_config(thread_id: str, threshold: float, message: str = "") -> dict:
    preview = message.strip()[:80] if message else ""
    return {
        "configurable": {
            "thread_id": thread_id,
            "confidence_threshold": threshold,
        },
        "run_name": f"fitness-coach-{thread_id}",
        "metadata": {
            "thread_id": thread_id,
            "confidence_threshold": threshold,
            "message_preview": preview,
        },
    }


def _shape_response(state: dict, thread_id: str, threshold: float) -> dict:
    top_route = state.get("route") or "COACH"
    confidence = float(state.get("confidence") or 0.0)
    rationale = state.get("routing_rationale") or ""
    raw_trace = state.get("trace") or []
    reply = _last_reply(state.get("messages") or [])
    is_clarify = _clarify_fired(raw_trace, confidence, threshold)
    ui_route = "CLARIFY" if is_clarify else top_route

    response: dict[str, Any] = {
        "thread_id": thread_id,
        "route": ui_route,
        "confidence": confidence,
        "rationale": rationale,
        "threshold": threshold,
        "trace": [_shape_event(ev) for ev in raw_trace],
        "content": _shape_content(ui_route, top_route, reply, state),
    }
    if is_clarify and top_route in _DOWNGRADABLE_ROUTES:
        response["downgradedFrom"] = top_route
    return response


_DOWNGRADABLE_ROUTES = {"COACH", "WORKOUT_GENERATE", "WORKOUT_LOG"}


def _last_reply(messages: list) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return ""


def _clarify_fired(trace: list[dict], confidence: float, threshold: float) -> bool:
    if any(ev.get("kind") == "clarify" for ev in trace):
        return True
    return confidence < threshold


# ---------------------------------------------------------------- content


def _shape_content(ui_route: str, top_route: str, reply: str, state: dict) -> dict:
    if ui_route == "CLARIFY":
        return _clarify_content(reply, state, top_route)
    if ui_route == "WORKOUT_GENERATE":
        return _workout_content(state.get("workout") or {}, state.get("trace") or [])
    if ui_route == "WORKOUT_LOG":
        return _log_content(state.get("log_entries") or [])
    return _coach_content(reply)


def _coach_content(reply: str) -> dict:
    return {"type": "coach", "prose": reply, "joints": [], "refs": []}


def _workout_content(workout: dict, trace: list[dict]) -> dict:
    if not workout:
        return {"type": "coach", "prose": "(no workout produced)", "joints": [], "refs": []}

    sections = [_shape_workout_section(sec) for sec in workout.get("sections", [])]
    duration = workout.get("duration_minutes")
    payload: dict[str, Any] = {
        "type": "workout",
        "title": workout.get("title") or "Workout",
        "meta": {
            "duration": f"≈{duration} min" if duration else "—",
            "equipment": _workout_equipment(workout),
            "focus": _workout_focus(workout) or "—",
        },
        "sections": sections,
        "joints": _workout_joints(workout),
    }
    recovered = _recovered_message(trace)
    if recovered:
        payload["recovered"] = recovered
    return payload


_SECTION_LABEL = {"warmup": "Warm-up", "main": "Main", "cooldown": "Cool-down"}


def _shape_workout_section(section: dict) -> dict:
    return {
        "name": _SECTION_LABEL.get(section.get("name", ""), section.get("name", "")),
        "items": [_shape_workout_item(it) for it in section.get("items", [])],
    }


def _shape_workout_item(item: dict) -> dict:
    shaped = {
        "id": item.get("exercise_id"),
        "sets": item.get("sets"),
        "reps": _format_reps(item.get("reps"), item.get("duration_seconds")),
        "rest": _format_rest(item.get("rest_seconds")),
    }
    if item.get("side_label"):
        shaped["side_label"] = item["side_label"]
    if item.get("paired"):
        shaped["paired"] = True
    return shaped


def _format_reps(reps: Optional[int], duration_seconds: Optional[int]) -> str:
    if reps:
        return str(reps)
    if duration_seconds:
        return f"{duration_seconds}s"
    return ""


def _format_rest(rest_seconds: Optional[int]) -> str:
    if not rest_seconds:
        return "—"
    return f"{rest_seconds}s"


def _workout_equipment(workout: dict) -> list[str]:
    seen: list[str] = []
    for sec in workout.get("sections", []):
        for it in sec.get("items", []):
            for eq in it.get("equipment", []) or []:
                if eq and eq not in seen:
                    seen.append(eq)
    return seen


def _workout_focus(workout: dict) -> str:
    muscles: list[str] = []
    for sec in workout.get("sections", []):
        if sec.get("name") != "main":
            continue
        for it in sec.get("items", []):
            ex = exercises.get_by_id(it.get("exercise_id") or "")
            for m in (ex or {}).get("muscle_groups", []) or []:
                if m and m not in muscles:
                    muscles.append(m)
    return " · ".join(muscles)


def _workout_joints(workout: dict) -> list[str]:
    ids: list[str] = []
    for sec in workout.get("sections", []):
        for it in sec.get("items", []):
            eid = it.get("exercise_id")
            if eid:
                ids.append(eid)
    return sorted(exercises.joints_for_exercise_ids(ids))


def _recovered_message(trace: list[dict]) -> str:
    for ev in trace:
        if ev.get("kind") == "recovery":
            return ev.get("label") or "Recovered from a tool failure during generation."
    return ""


def _log_content(entries: list[dict]) -> dict:
    return {"type": "log", "entries": [_shape_log_entry(e) for e in entries]}


def _shape_log_entry(entry: dict) -> dict:
    return {
        "raw": entry.get("raw_name") or "",
        "matched_id": entry.get("matched_id"),
        "matched_name": entry.get("matched_name"),
        "score": _score_to_unit(entry.get("match_score")),
        "sets": entry.get("sets"),
        "reps": entry.get("reps"),
        "weight": entry.get("weight"),
        "unit": entry.get("weight_unit"),
    }


def _score_to_unit(raw_score: Any) -> float:
    if raw_score is None:
        return 0.0
    return float(raw_score) / 100.0


_ROUTE_BUTTON_LABEL = {
    "COACH": "Answer as coaching",
    "WORKOUT_GENERATE": "Build a workout",
    "WORKOUT_LOG": "Log a set",
}


def _clarify_content(reply: str, state: dict, top_route: str) -> dict:
    raw_options = state.get("clarify_options") or []
    ordered = _ordered_clarify_routes(raw_options, top_route)
    buttons = [_ROUTE_BUTTON_LABEL[r] for r in ordered if r in _ROUTE_BUTTON_LABEL]
    if not buttons:
        buttons = list(_ROUTE_BUTTON_LABEL.values())
    return {
        "type": "clarify",
        "question": reply or "Could you tell me a bit more about what you'd like to do?",
        "options": buttons,
    }


def _ordered_clarify_routes(options: list[str], top_route: str) -> list[str]:
    seen: list[str] = []
    if top_route in _ROUTE_BUTTON_LABEL:
        seen.append(top_route)
    for r in options:
        if r in _ROUTE_BUTTON_LABEL and r not in seen:
            seen.append(r)
    for r in _ROUTE_BUTTON_LABEL:
        if r not in seen:
            seen.append(r)
    return seen


# ---------------------------------------------------------------- trace


def _shape_event(ev: dict) -> dict:
    kind = ev.get("kind", "")
    if kind == "route":
        return _shape_route_event(ev)
    if kind == "tool_call":
        return _shape_tool_event(ev)
    if kind == "recovery":
        return _shape_recover_event(ev)
    if kind == "agent":
        return {"kind": "agent", "label": ev.get("label") or "agent"}
    if kind == "clarify":
        return _shape_clarify_event(ev)
    return {"kind": "note", "label": ev.get("label") or ""}


def _shape_route_event(ev: dict) -> dict:
    detail = ev.get("detail") or {}
    route = detail.get("route", "?")
    confidence = detail.get("confidence", 0.0)
    return {
        "kind": "router",
        "label": "route_query",
        "out": f"{route} · {float(confidence):.2f}",
    }


def _shape_tool_event(ev: dict) -> dict:
    detail = ev.get("detail") or {}
    label = ev.get("label") or "tool"
    if "args" in detail:
        count = detail.get("count")
        out: dict[str, Any] = {
            "kind": "tool",
            "label": "search_exercises",
            "input": detail["args"],
        }
        if count is not None:
            out["out"] = f"{count} results"
            out["count"] = count
        return out
    if "score" in detail:
        return {
            "kind": "tool",
            "label": "fuzzy_match",
            "out": f"score {float(detail['score']):.0f}",
        }
    if "title" in detail:
        return {
            "kind": "tool",
            "label": "build_workout",
            "out": f"ok · {detail.get('title') or ''}".strip(" ·"),
        }
    return {"kind": "tool", "label": label}


def _shape_recover_event(ev: dict) -> dict:
    detail = ev.get("detail") or {}
    label = ev.get("label") or "fallback"
    if "args" in detail:
        return {
            "kind": "recover",
            "label": "fallback",
            "out": "0 results → relaxing filters and re-searching",
            "count": 0,
        }
    if "message" in detail:
        return {"kind": "recover", "label": "rejected", "out": str(detail["message"])}
    return {"kind": "recover", "label": "fallback", "out": label}


def _shape_clarify_event(ev: dict) -> dict:
    detail = ev.get("detail") or {}
    confidence = detail.get("confidence")
    if confidence is None:
        return {"kind": "note", "label": "gate", "out": ev.get("label") or "CLARIFY"}
    return {
        "kind": "note",
        "label": "gate",
        "out": f"{float(confidence):.2f} below threshold → CLARIFY",
    }


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
