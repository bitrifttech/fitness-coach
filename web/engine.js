/* engine.js — real backend client for the multi-agent console.
   Exposes window.FitEngine with:
     - EXERCISES, byId: dataset loaded from /api/exercises (mutated in place
       so components.jsx's `const EX = window.FitEngine.byId` reference stays live)
     - ready: a promise that resolves once the dataset is loaded
     - route(text, threshold, threadId): POSTs /api/chat and returns the turn
     - routeStream(text, threshold, threadId, onEvent): SSE stream with partial updates
*/
(function () {
  "use strict";

  const EXERCISES = [];
  const byId = {};

  async function loadExercises() {
    const r = await fetch("/api/exercises");
    if (!r.ok) throw new Error("failed to load /api/exercises: " + r.status);
    const data = await r.json();
    EXERCISES.length = 0;
    for (const ex of data) {
      EXERCISES.push(ex);
      byId[ex.id] = ex;
    }
  }

  async function route(text, threshold, threadId) {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, thread_id: threadId, threshold }),
    });
    if (!r.ok) {
      const body = await r.text().catch(() => "");
      throw new Error("api/chat " + r.status + ": " + body);
    }
    return r.json();
  }

  function parseSseChunk(buffer, onEvent) {
    const lines = buffer.split("\n");
    const rest = lines.pop() || "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (payload === "[DONE]") return { done: true, rest };
      try {
        onEvent(JSON.parse(payload));
      } catch (_) { /* ignore malformed */ }
    }
    return { done: false, rest };
  }

  async function routeStream(text, threshold, threadId, onEvent) {
    const r = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, thread_id: threadId, threshold }),
    });
    if (!r.ok) {
      const body = await r.text().catch(() => "");
      throw new Error("api/chat/stream " + r.status + ": " + body);
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalTurn = null;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseChunk(buffer, (ev) => {
        if (ev.node === "__final__") finalTurn = ev.update;
        onEvent(ev);
      });
      buffer = parsed.rest;
      if (parsed.done) break;
    }
    if (!finalTurn) throw new Error("stream ended without final turn");
    return finalTurn;
  }

  const ready = loadExercises();

  window.FitEngine = { EXERCISES, byId, route, routeStream, ready };
})();
