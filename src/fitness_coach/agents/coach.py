"""Coach sub-agent: a small standalone StateGraph for education/advice answers.

Kept as its own compiled graph (not an inline function) so the hub composes
graphs, per the architecture requirement.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from ..llm import get_chat_model
from ..state import HubState

_SYSTEM_PROMPT = """You are a knowledgeable, concise fitness coach.
Answer the user's question about training, anatomy, form, or programming.
Be accurate and practical. If a question is outside fitness, say so briefly.
Do not fabricate specific exercises from a database — speak from general knowledge.
"""


def _respond(state: HubState) -> dict:
    model = get_chat_model(temperature=0.3)
    messages = [SystemMessage(content=_SYSTEM_PROMPT), *state["messages"]]
    reply = model.invoke(messages)

    trace = list(state.get("trace") or [])
    trace.append({"kind": "agent", "label": "coach answered", "detail": {}})
    return {"messages": [reply], "trace": trace}


def build_coach_graph():
    graph = StateGraph(HubState)
    graph.add_node("respond", _respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph.compile()
