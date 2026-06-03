"""Workout generator sub-agent.

Uses LangGraph's prebuilt ``create_react_agent`` for the tool-calling loop
(search_exercises -> build_workout), wrapped in a thin node that:
  * prepends a system prompt,
  * runs the ReAct loop,
  * extracts the structured Workout + per-tool trace events,
  * surfaces empty-search recoveries so resilience is visible.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent

from .. import exercises
from ..llm import get_chat_model
from ..state import HubState
from ..tools import GENERATOR_TOOLS

_VOCAB = exercises.vocabulary()

_SYSTEM_PROMPT = f"""You build safe, structured workouts using ONLY the exercise library.

The library only understands these facet values — translate the user's request
into them (e.g. "upper body" -> chest/back/shoulders/arms muscles below):

- muscle_groups: {_VOCAB["muscle_groups"]}
- equipment: {_VOCAB["equipment"]}

Body-part focus (critical):
- "back workout" → search with muscle_groups like lats, upper back, lower back, traps.
  The **main** block must be mostly true back exercises — not a chest/arms day with one row.
  At most one accessory curl/extension unless the user asked for arms too.
- "leg workout" → quads, glutes, hamstrings, calves. "chest workout" → chest-focused, etc.

Process (always):
1. Call search_exercises with valid muscle_groups / equipment from the lists above.
   Prefer searching by muscle_groups (and equipment if specified). Avoid passing
   colloquial terms like "upper body" — expand them to specific muscles.
   If the user mentions an injury or joint limitation (shoulder, knee, etc.),
   pass avoid_joints to search_exercises AND build_workout so those joints are
   never loaded.
2. If the user named **specific equipment** (e.g. "rowing machine", "dumbbells only")
   and search returns count==0 OR ``unmatched_equipment`` is non-empty:
   - Do **NOT** silently drop that equipment and build with something else.
   - Explain clearly that the requested equipment is not in the library.
   - Mention the closest available alternatives from the equipment list above
     (e.g. "Chest Supported Row Machine" for row-style work — not a rowing machine).
   - Do **NOT** call build_workout unless the remaining search results actually
     use equipment the user asked for, or they did not require specific equipment.
3. For other empty searches (no equipment constraint), relax one filter and retry.
   If still empty, explain what is unavailable.
4. Once you have suitable exercises, call build_workout with a warmup, main
   block, and cooldown. Use ONLY exercise ids returned by search_exercises.
   Pass the same avoid_joints to build_workout when injury avoidance applies.
   Single-side (unilateral) exercises are auto-expanded to both sides in the card.
5. After build_workout succeeds, write a short friendly summary for the user in Markdown
   (use **bold** for emphasis and bullet lists when helpful).

Respect the requested duration and equipment constraints.

If the user wants to adjust or modify a previous workout but has not said what
they did (exercises, duration, equipment, intensity), ask briefly what they
performed before calling search_exercises or build_workout.
"""

_BODY_FOCUS: dict[str, set[str]] = {
    "back": {"lats", "upper back", "lower back", "traps"},
    "leg": {"quads", "glutes", "hamstrings", "calves"},
    "chest": {"chest"},
    "shoulder": {"deltoids", "shoulders"},
    "arm": {"biceps", "triceps"},
}
_FOCUS_MIN_MAIN_RATIO = 0.6
_EQUIPMENT_PHRASES = (
    "rowing machine",
    "chest supported row machine",
    "lat pulldown",
    "dumbbell",
    "barbell",
    "kettlebell",
    "cable",
    "bodyweight",
    "resistance band",
)


def _last_user_text(state: HubState) -> str:
    for msg in reversed(state.get("messages") or []):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
        if getattr(msg, "type", None) == "human":
            return str(msg.content)
    return ""


def _explicit_equipment_requests(text: str) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    for phrase in _EQUIPMENT_PHRASES:
        if phrase in lower and phrase not in found:
            found.append(phrase)
    return found


def _unmatched_user_equipment(text: str) -> list[str]:
    terms = _explicit_equipment_requests(text)
    if not terms:
        return []
    return exercises.check_equipment_terms(terms)["unmatched"]


def _parse_body_focus(text: str) -> set[str] | None:
    lower = text.lower()
    if re.search(r"\bback\b", lower) and re.search(
        r"\b(workout|session|day|routine|training)\b", lower
    ):
        return _BODY_FOCUS["back"]
    if re.search(r"\bleg\b", lower) and re.search(
        r"\b(workout|session|day|routine|training)\b", lower
    ):
        return _BODY_FOCUS["leg"]
    if re.search(r"\bchest\b", lower) and re.search(
        r"\b(workout|session|day|routine|training)\b", lower
    ):
        return _BODY_FOCUS["chest"]
    return None


def _main_items(workout: dict) -> list[dict]:
    for sec in workout.get("sections", []):
        if sec.get("name") == "main":
            return sec.get("items", [])
    return []


def _item_hits_focus(item: dict, focus: set[str]) -> bool:
    ex = exercises.get_by_id(item.get("exercise_id") or "")
    if not ex:
        return False
    muscles = {m.lower() for m in ex.get("muscle_groups", [])}
    return bool(muscles & focus)


def _workout_meets_focus(workout: dict, focus: set[str]) -> bool:
    items = _main_items(workout)
    if not items:
        return True
    hits = sum(1 for it in items if _item_hits_focus(it, focus))
    return hits / len(items) >= _FOCUS_MIN_MAIN_RATIO


def _collect_workout_equipment(workout: dict) -> list[str]:
    equip: list[str] = []
    for sec in workout.get("sections", []):
        for it in sec.get("items", []):
            equip.extend(it.get("equipment") or [])
    return equip


def _failed_equipment_filters(trace: list) -> list[list[str]]:
    """Equipment filters from searches that returned zero results."""
    failed: list[list[str]] = []
    for ev in trace:
        if ev.get("kind") != "tool_call":
            continue
        detail = ev.get("detail") or {}
        if detail.get("count") != 0:
            continue
        args = detail.get("args") or {}
        if args.get("equipment"):
            failed.append(args["equipment"])
    return failed


def _unmatched_equipment_from_trace(trace: list) -> list[str]:
    terms: list[str] = []
    for ev in trace:
        if ev.get("kind") != "recovery":
            continue
        detail = ev.get("detail") or {}
        for term in detail.get("unmatched_equipment") or []:
            if term not in terms:
                terms.append(term)
    return terms


def _workout_honors_equipment(workout: dict, required_terms: list[str]) -> bool:
    if not required_terms:
        return True
    workout_equip = _collect_workout_equipment(workout)
    return exercises._matches_any(required_terms, workout_equip)


def _strip_workout_on_equipment_violation(
    workout: dict | None, trace: list, user_text: str = ""
) -> tuple[dict | None, str | None]:
    """Drop workouts built after ignoring failed or unavailable equipment."""
    if not workout:
        return workout, None
    required: list[str] = []
    for terms in _failed_equipment_filters(trace):
        required.extend(terms)
    for term in _unmatched_equipment_from_trace(trace):
        if term not in required:
            required.append(term)
    for term in _unmatched_user_equipment(user_text):
        if term not in required:
            required.append(term)
    seen: list[str] = []
    for term in required:
        if term not in seen:
            seen.append(term)
    for terms in [seen]:
        if not _workout_honors_equipment(workout, terms):
            return None, ", ".join(terms)
    return workout, None


def _strip_workout_on_focus_violation(
    workout: dict | None, user_text: str
) -> tuple[dict | None, str | None]:
    if not workout:
        return workout, None
    focus = _parse_body_focus(user_text)
    if not focus or _workout_meets_focus(workout, focus):
        return workout, None
    label = next((k for k, v in _BODY_FOCUS.items() if v == focus), "requested")
    return None, label


def _parse_tool_content(content: Any) -> Any:
    if isinstance(content, (dict, list)):
        return content
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content


def _generate(state: HubState) -> dict:
    agent = create_react_agent(get_chat_model(temperature=0.2), GENERATOR_TOOLS)
    result = agent.invoke(
        {"messages": [SystemMessage(content=_SYSTEM_PROMPT), *state["messages"]]}
    )
    new_messages = result["messages"]

    trace = list(state.get("trace") or [])
    workout: dict | None = None

    # Pair each tool call (AIMessage) with its result (ToolMessage) for the trace.
    pending_calls: dict[str, dict] = {}
    for msg in new_messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for call in msg.tool_calls:
                pending_calls[call["id"]] = call
        elif isinstance(msg, ToolMessage):
            call = pending_calls.get(msg.tool_call_id, {})
            payload = _parse_tool_content(msg.content)
            name = call.get("name", msg.name or "tool")

            if name == "search_exercises":
                count = payload.get("count") if isinstance(payload, dict) else None
                unmatched = payload.get("unmatched_equipment") if isinstance(payload, dict) else []
                trace.append(
                    {
                        "kind": "tool_call",
                        "label": f"search_exercises -> {count} results",
                        "detail": {"args": call.get("args", {}), "count": count},
                    }
                )
                if unmatched:
                    trace.append(
                        {
                            "kind": "recovery",
                            "label": f"equipment not in library: {', '.join(unmatched)}",
                            "detail": {"unmatched_equipment": unmatched, "args": call.get("args", {})},
                        }
                    )
                elif count == 0:
                    trace.append(
                        {
                            "kind": "recovery",
                            "label": "empty search result — agent recovering (no hallucination)",
                            "detail": {"args": call.get("args", {})},
                        }
                    )
            elif name == "build_workout":
                if isinstance(payload, dict) and payload.get("error"):
                    trace.append(
                        {
                            "kind": "recovery",
                            "label": f"build_workout rejected: {payload.get('error')}",
                            "detail": payload,
                        }
                    )
                else:
                    workout = payload if isinstance(payload, dict) else None
                    trace.append(
                        {
                            "kind": "tool_call",
                            "label": "build_workout -> ok",
                            "detail": {"title": workout.get("title") if workout else None},
                        }
                    )

    # The agent's final natural-language summary is the last AIMessage with text.
    final_message = next(
        (m for m in reversed(new_messages) if isinstance(m, AIMessage) and m.content),
        new_messages[-1],
    )

    user_text = _last_user_text(state)

    workout, violated = _strip_workout_on_equipment_violation(workout, trace, user_text)
    if violated:
        alt_hint = ""
        if "row" in violated.lower():
            row_alts = [e for e in exercises.vocabulary()["equipment"] if "row" in e.lower()]
            if row_alts:
                alt_hint = f" Closest row-style option: **{row_alts[0]}**."
        final_message = AIMessage(
            content=(
                f"I couldn't build a workout using **{violated}** — that equipment isn't "
                f"in our exercise library.{alt_hint} "
                "Tell me if you'd like a back workout with available equipment instead."
            )
        )
    else:
        workout, focus_violation = _strip_workout_on_focus_violation(workout, user_text)
        if focus_violation:
            final_message = AIMessage(
                content=(
                    f"That plan wasn't **{focus_violation}-focused** enough (too much chest/arms). "
                    f"I can rebuild a true {focus_violation} session with the equipment we have — "
                    "say the word or name your equipment."
                )
            )

    out: dict = {"messages": [final_message], "trace": trace}
    if workout is not None:
        out["workout"] = workout
    return out


def build_generator_graph():
    graph = StateGraph(HubState)
    graph.add_node("generate", _generate)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", END)
    return graph.compile()
