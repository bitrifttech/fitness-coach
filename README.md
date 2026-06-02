# Fitness Coaching Multi-Agent System

A multi-agent fitness coach built on **LangGraph**. A hub agent classifies each
message with **LLM structured output** and routes it to one of three specialized
sub-agents, each implemented as its own composed graph. Ships with a FastAPI
backend and a single-page "glass box" demo UI that exposes the routing decision,
confidence, and tool calls for every turn.

```
                       ┌─────────────────────────────┐
   user turn ─────────▶│  router (structured output) │
                       │   route + confidence + why  │
                       └──────────────┬──────────────┘
                                      │ confidence gate
            ┌───────────────┬─────────┴─────────┬───────────────┐
            ▼               ▼                   ▼               ▼
        clarify          coach            generator         logger
     (low conf.)     (Q&A graph)      (ReAct + tools)   (extract+fuzzy)
            └───────────────┴─────────┬─────────┴───────────────┘
                                      ▼
                              reply + trace + payload
```

## Routes

| Route | Example | Sub-agent |
|-------|---------|-----------|
| `COACH` | "What muscles does a deadlift work?" | LLM Q&A graph |
| `WORKOUT_GENERATE` | "Build me a 30 min upper body session with dumbbells" | tool-calling ReAct agent (`search_exercises`, `build_workout`) |
| `WORKOUT_LOG` | "I just did 3x10 bench press at 185 lbs" | structured extraction + fuzzy match |
| `CLARIFY` (fallback) | "Bench press" | asks the user to disambiguate |

## Architecture

- **Hub** (`src/fitness_coach/hub.py`) — a typed `StateGraph` (`HubState`) with
  explicit edges. A conditional edge (`route_gate`) reads the router's confidence
  and either dispatches to a sub-agent or diverts to `clarify`.
- **Router** (`router.py`) — one LLM call via `with_structured_output(RoutingDecision)`.
  Returns `route`, a calibrated `confidence` (0–1), a `rationale`, and
  `clarify_options`. No regex/keyword matching.
- **Confidence policy** — turns below `CONFIDENCE_THRESHOLD` (default `0.6`) go to
  `clarify`, which asks the user which route they meant instead of silently
  committing. Threshold is an explicit, configurable knob.
- **Sub-agents** (`agents/`) — each is a separately compiled graph composed into
  the hub as a node (not an inline function):
  - `coach` — single-node Q&A graph.
  - `generator` — LangGraph prebuilt `create_react_agent` running the
    `search_exercises → build_workout` tool loop, grounded with the dataset's
    real muscle/equipment vocabulary so it picks valid facets.
  - `logger` — two-node graph: structured extraction → deterministic
    `rapidfuzz` matching of colloquial names to canonical exercises.
- **Tools** (`tools.py`) — `search_exercises` and `build_workout`, each with a
  Pydantic input schema and field descriptions.
- **Memory** — a `MemorySaver` checkpointer keyed on `thread_id`, so multi-turn
  context and the clarify-then-retry flow work across requests.
- **Trace** — every node appends `TraceEvent`s (route, tool calls, recoveries),
  surfaced under each assistant message as an expandable "Show reasoning" panel.

## Resilience

- **No search results** (e.g. equipment not in the dataset) → the tool returns
  `{count: 0, results: []}`, and the generator's prompt forbids inventing
  exercises: it relaxes a filter and retries, then explains what's unavailable.
  A `recovery` trace event makes this visible.
- **Invalid tool call** (unknown `exercise_id`, bad schema) → Pydantic validation
  and an explicit id check return a structured `error` payload the agent can act
  on, rather than throwing or fabricating a workout.
- **No confident fuzzy match** for a logged exercise → the entry is logged
  as-is with a `recovery` note instead of forcing a wrong match.

## Running locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # add -dev for tests
cp .env.example .env                    # add your OPENROUTER_API_KEY
uvicorn app:app --reload                # open http://localhost:8000
```

### API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat` | run one turn → `{reply, route, confidence, rationale, trace, workout, log_entries, thread_id}` |
| `POST` | `/api/chat/stream` | same, streamed as Server-Sent Events |
| `GET` | `/api/session/{thread_id}/logs` | accumulated `WORKOUT_LOG` entries |
| `GET` | `/health` | liveness probe |
| `GET` | `/` | demo chat UI |

```bash
curl -s -X POST localhost:8000/api/chat -H 'Content-Type: application/json' \
  -d '{"message":"Build me a 20 min upper body session with dumbbells"}'
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Two critical paths are covered (chosen because they are the highest-risk parts
of the system):

1. **Routing + low-confidence fallback** (`tests/test_routing.py`) — every
   request flows through the router, and a silent misroute is the worst failure.
   Tests assert the confidence gate diverts ambiguous turns to `clarify` and that
   the router emits a well-formed decision + trace (LLM mocked for determinism).
2. **Resilience** (`tests/test_resilience.py`) — the two failure modes the brief
   calls out. Tests assert empty searches return a recoverable signal (not a
   crash), invalid exercise ids are rejected (not fabricated), and fuzzy matching
   maps "bench press" to a canonical exercise.

These are deterministic (no live LLM calls) so they're cheap and CI-safe.

## How I would evaluate this system in production

**Routing quality is the top metric.** I'd maintain a labeled set of real user
messages (including the ambiguous ones) and track **routing accuracy** and a
confusion matrix across the four routes. The most important derived metrics are
the **misroute rate** (routed confidently to the wrong agent — the silent
failure that erodes trust) and the **clarify rate** (how often we fall back).
Those trade off against each other via the confidence threshold: too low and we
misroute, too high and we nag users with clarifications. I'd tune the threshold
against this set and re-check it whenever the model id changes, since confidence
calibration is model-specific. Logging the router's `confidence` and `rationale`
on every turn (already in the trace) makes this analysis possible offline.

**Per-agent task success.** For the generator: rate of workouts that pass schema
validation, respect the requested duration/equipment, and use only real exercise
ids (a hallucinated-id rate of essentially zero is the bar — the `build_workout`
guard enforces it, and I'd alert if it ever rejects in production, since that
means the model is drifting). For the logger: extraction completeness (did we
capture sets/reps/weight the user stated?) and a distribution of fuzzy
**match scores** — a rising share of low-score or unmatched entries signals the
exercise vocabulary has drifted from how users actually talk, which is a cue to
expand synonyms or the dataset.

**Failure modes to monitor.** (1) Empty-search recoveries — a spike means users
want equipment/movements we don't have, which is product signal, not just an
error. (2) Tool-call retries and validation rejections per turn — rising retries
mean the model is struggling with the tool schema. (3) LLM/provider errors,
latency (p50/p95 per route — the generator's tool loop is the slowest), and token
cost per turn. (4) Multi-turn breakage — clarify turns that don't resolve on the
next message, indicating the checkpointed context isn't being used well.

**How I'd know it's working.** A healthy system shows high routing accuracy with
a low, stable clarify rate; near-zero hallucinated ids; fuzzy-match scores
clustered high; and recoveries that correlate with genuinely out-of-scope
requests rather than valid ones we mishandle. I'd wire the existing structured
trace into a real tracer (Langfuse or OpenTelemetry) so each turn is one span
tree — router decision → sub-agent → tool calls — sampled for human review, with
automated LLM-as-judge scoring of a daily slice for coaching accuracy and
workout safety (e.g. flagging joint-overloading combinations using
`joints_loaded`).

## Project layout

```
app.py                     FastAPI entrypoint (+ serves the demo UI)
web/index.html             single-page demo UI
data/exercises.json        50-exercise dataset
src/fitness_coach/
  config.py  llm.py  state.py  exercises.py  tools.py  router.py
  hub.py  service.py
  agents/    coach.py  generator.py  logger.py
tests/       test_routing.py  test_resilience.py
```
