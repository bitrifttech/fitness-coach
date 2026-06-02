"""Workout logger sub-agent.

Two-step graph:
  1. extract: LLM structured output parses sets/reps/weight from natural language.
  2. match: deterministic fuzzy match maps each spoken name to a canonical
     exercise (rapidfuzz), so "bench press" -> "Barbell Flat Bench Press".

No tool-calling loop is needed; extraction + a local matcher is more reliable
and cheaper than letting the model call a search tool here.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from .. import exercises
from ..llm import get_chat_model
from ..state import HubState

_SYSTEM_PROMPT = """Extract every exercise the user reports having performed.
For each, capture: the exercise name as spoken, sets, reps, weight, and weight
unit (lb/kg) when present. If a value is not stated, leave it null. Do not
invent values. Return only what the user actually did (past tense)."""


class ParsedSet(BaseModel):
    raw_name: str = Field(description="Exercise name exactly as the user said it.")
    sets: Optional[int] = Field(None, description="Number of sets.")
    reps: Optional[int] = Field(None, description="Reps per set.")
    weight: Optional[float] = Field(None, description="Weight value.")
    weight_unit: Optional[str] = Field(None, description="Weight unit, e.g. 'lb' or 'kg'.")


class ExtractedLog(BaseModel):
    entries: list[ParsedSet] = Field(default_factory=list)


def _extract(state: HubState) -> dict:
    model = get_chat_model(temperature=0.0).with_structured_output(ExtractedLog)
    extracted: ExtractedLog = model.invoke(
        [SystemMessage(content=_SYSTEM_PROMPT), *state["messages"]]
    )
    trace = list(state.get("trace") or [])
    trace.append(
        {
            "kind": "agent",
            "label": f"extracted {len(extracted.entries)} log entr(ies)",
            "detail": {},
        }
    )
    return {
        "log_entries": [e.model_dump() for e in extracted.entries],
        "trace": trace,
    }


def _match(state: HubState) -> dict:
    entries = list(state.get("log_entries") or [])
    trace = list(state.get("trace") or [])
    matched: list[dict] = []

    for entry in entries:
        result = exercises.fuzzy_match(entry["raw_name"])
        if result is None:
            entry.update({"matched_id": None, "matched_name": None, "match_score": 0.0})
            trace.append(
                {
                    "kind": "recovery",
                    "label": f"no confident match for '{entry['raw_name']}' — logged as-is",
                    "detail": {"raw_name": entry["raw_name"]},
                }
            )
        else:
            ex, score = result
            entry.update(
                {"matched_id": ex["id"], "matched_name": ex["name"], "match_score": score}
            )
            trace.append(
                {
                    "kind": "tool_call",
                    "label": f"matched '{entry['raw_name']}' -> {ex['name']} ({score:.0f})",
                    "detail": {"score": score},
                }
            )
        matched.append(entry)

    summary = _summarize(matched)
    return {"log_entries": matched, "messages": [AIMessage(content=summary)], "trace": trace}


def _summarize(entries: list[dict]) -> str:
    if not entries:
        return "I couldn't find any workout details to log. Tell me what you did, e.g. '3x10 bench press at 185 lbs'."
    lines = ["Logged your workout:"]
    for e in entries:
        name = e.get("matched_name") or e.get("raw_name")
        bits = []
        if e.get("sets") and e.get("reps"):
            bits.append(f"{e['sets']}x{e['reps']}")
        if e.get("weight"):
            bits.append(f"{e['weight']:g}{e.get('weight_unit') or ''}")
        detail = " ".join(bits)
        lines.append(f"- {name}{(' — ' + detail) if detail else ''}")
    return "\n".join(lines)


def build_logger_graph():
    graph = StateGraph(HubState)
    graph.add_node("extract", _extract)
    graph.add_node("match", _match)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "match")
    graph.add_edge("match", END)
    return graph.compile()
