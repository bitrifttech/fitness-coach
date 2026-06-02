/* engine.js — real backend client for the multi-agent console.
   Exposes window.FitEngine with:
     - EXERCISES, byId: dataset loaded from /api/exercises (mutated in place
       so components.jsx's `const EX = window.FitEngine.byId` reference stays live)
     - ready: a promise that resolves once the dataset is loaded
     - route(text, threshold, threadId): POSTs /api/chat and returns the turn
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

  const ready = loadExercises();

  window.FitEngine = { EXERCISES, byId, route, ready };
})();
