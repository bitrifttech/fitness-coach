"""FastAPI entrypoint for the fitness coaching multi-agent system.

Exposes the hub graph over HTTP and serves the multi-agent console web view.

    GET  /health                       liveness probe
    POST /api/chat                     run one turn, return UI-contract response
    POST /api/chat/stream              same, streamed as Server-Sent Events
    GET  /api/session/{thread}/logs    accumulated WORKOUT_LOG entries
    GET  /api/exercises                full exercise dataset (UI lookup table)
    GET  /                             coach console
    GET  /{asset}                      sibling JS/JSX/CSS files from web/
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fitness_coach import exercises  # noqa: E402
from fitness_coach.service import run_turn, session_logs, stream_turn  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent / "web"
WEB_ASSET_SUFFIXES = {".js", ".jsx", ".css", ".html", ".svg", ".ico", ".png"}

app = FastAPI(title="Fitness Coach Multi-Agent", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str | None = Field(None, description="Conversation id; generated if omitted.")
    threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Per-turn confidence floor; overrides server default."
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    thread_id = req.thread_id or str(uuid.uuid4())
    return run_turn(req.message, thread_id, req.threshold)


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    thread_id = req.thread_id or str(uuid.uuid4())

    async def event_gen():
        yield f"data: {json.dumps({'node': '__thread__', 'thread_id': thread_id})}\n\n"
        async for event in stream_turn(req.message, thread_id, req.threshold):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/api/session/{thread_id}/logs")
def logs(thread_id: str) -> dict:
    return {"thread_id": thread_id, "log_entries": session_logs(thread_id)}


@app.get("/api/exercises")
def exercises_endpoint() -> list[dict]:
    return exercises.all_exercises()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/{asset_path:path}")
def web_asset(asset_path: str) -> FileResponse:
    candidate = (WEB_DIR / asset_path).resolve()
    if WEB_DIR.resolve() not in candidate.parents and candidate != WEB_DIR.resolve():
        raise HTTPException(status_code=404)
    if candidate.suffix not in WEB_ASSET_SUFFIXES or not candidate.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(candidate)
