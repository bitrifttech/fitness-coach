"""FastAPI entrypoint for the fitness coaching multi-agent system.

Exposes the hub graph over HTTP and serves a minimal single-page demo UI.

    GET  /health                       liveness probe
    POST /api/chat                     run one turn, return structured response
    POST /api/chat/stream              same, streamed as Server-Sent Events
    GET  /api/session/{thread}/logs    accumulated WORKOUT_LOG entries
    GET  /                             demo chat UI
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fitness_coach.service import run_turn, session_logs, stream_turn  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title="Fitness Coach Multi-Agent", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str | None = Field(None, description="Conversation id; generated if omitted.")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    thread_id = req.thread_id or str(uuid.uuid4())
    result = run_turn(req.message, thread_id)
    result["thread_id"] = thread_id
    return result


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    thread_id = req.thread_id or str(uuid.uuid4())

    async def event_gen():
        yield f"data: {json.dumps({'node': '__thread__', 'thread_id': thread_id})}\n\n"
        async for event in stream_turn(req.message, thread_id):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/api/session/{thread_id}/logs")
def logs(thread_id: str) -> dict:
    return {"thread_id": thread_id, "log_entries": session_logs(thread_id)}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
