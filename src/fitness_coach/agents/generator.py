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
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
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

Process (always):
1. Call search_exercises with valid muscle_groups / equipment from the lists above.
   Prefer searching by muscle_groups (and equipment if specified). Avoid passing
   colloquial terms like "upper body" — expand them to specific muscles.
2. If results come back EMPTY (count == 0), DO NOT invent exercises. Relax one
   filter (e.g. drop equipment, or try a related muscle) and search again. Only
   if still empty, explain what is unavailable and offer the closest alternative.
3. Once you have suitable exercises, call build_workout with a warmup, main
   block, and cooldown. Use ONLY exercise ids returned by search_exercises.
4. After build_workout succeeds, write a short friendly summary for the user.

Respect the requested duration and equipment constraints.
"""


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
                trace.append(
                    {
                        "kind": "tool_call",
                        "label": f"search_exercises -> {count} results",
                        "detail": {"args": call.get("args", {}), "count": count},
                    }
                )
                if count == 0:
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
