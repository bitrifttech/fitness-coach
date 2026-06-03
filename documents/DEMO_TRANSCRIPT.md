# Demo Transcript

Live demo: [Railway deployment](https://fitness-coach-production-742e.up.railway.app)  
Observability: [LangSmith project `fitness-coach`](https://smith.langchain.com)

Each turn below shows the user message, route, confidence, and a summary of the response. Expand **Show reasoning** in the UI to see the full trace (router decision, tool calls, recoveries).

---

## 1. COACH — anatomy question (Markdown)

**User:** `What muscles does a deadlift work?`

**Route:** `COACH` · confidence ~0.90

**Response:** Markdown-formatted prose — **bold** muscle groups, lists. No workout card.

**Trace:**
- `route` → COACH (confidence 0.90)
- `agent` → coach answered

---

## 2. WORKOUT_GENERATE — structured session

**User:** `Build me a 30 min upper body session with dumbbells`

**Route:** `WORKOUT_GENERATE` · confidence ~0.90

**Response:** Workout card with Warm-up / Main / Cool-down sections, sets×reps, rest, equipment. Joints-loaded chips shown under the title.

**Trace:**
- `route` → WORKOUT_GENERATE
- `tool` → search_exercises → N results
- `tool` → build_workout → ok

---

## 3. WORKOUT_LOG — fuzzy match (multi-entry)

**User:** `I just did 3x10 bench at 185 lb and 3x12 dumbbell rows at 70 lb`

**Route:** `WORKOUT_LOG` · confidence ~0.90

**Response:** Confirmation card with fuzzy-matched exercises, sets/reps/weight. Both entries appear in the Session Log sidebar.

**Trace:**
- `route` → WORKOUT_LOG
- `agent` → extracted 1 log entr(y)
- `tool` → fuzzy_match → score ~77

---

## 4. CLARIFY — ambiguous input

**User:** `Bench press`

**Route:** `CLARIFY` · confidence ~0.50 (below threshold 0.60)

**Response:** Clarify card asking whether the user wants coaching, workout generation, or logging. Candidate buttons offered.

**Trace:**
- `route` → COACH or WORKOUT_* at low confidence
- `note` → gate: 0.50 below threshold → CLARIFY

---

## 5. ADJUST — not logging

**User:** `I did a workout yesterday, can you adjust it?`

**Route:** `CLARIFY` · confidence capped below threshold (not `WORKOUT_LOG`)

**Response:** Clarify card — asks what you did or offers **Build or adjust a workout** / coaching. Does **not** send to the logger.

**Trace:**
- `route` → WORKOUT_GENERATE at low confidence (or corrected from LOG)
- `note` → gate → CLARIFY

---

## 6. RESILIENCE — equipment not in library

**User:** `Build me a back workout using a rowing machine`

**Route:** `WORKOUT_GENERATE`

**Response:** No workout card with wrong equipment. Prose explains that a **rowing machine** is not in the library, suggests the closest row-style option (**Chest Supported Row Machine**), and offers to build with available equipment. Trace shows `unmatched_equipment` / equipment recovery — not a silent dumbbell fallback.

**Trace:**
- `tool` → search_exercises → 0 results, `unmatched_equipment: ["rowing machine"]`
- `recover` → equipment not in library
- No `build_workout` with exercises that ignore the user's equipment request

---

## 7. INJURY — joint avoidance

**User:** `Build a 25 min leg workout but avoid loading my shoulder`

**Route:** `WORKOUT_GENERATE`

**Response:** Leg-focused workout with no shoulder-loading exercises. Workout joints chips exclude `shoulder`.

**Trace:**
- `tool` → search_exercises with `avoid_joints: ["shoulder"]`
- `build_workout` passes same avoid list; rejects any accidental shoulder load

---

## Streaming (stretch)

The console uses `POST /api/chat/stream` (SSE). While a turn runs, the assistant placeholder updates as each graph node completes (`router` → `generator` / `coach` / `logger`), then resolves to the final card when `__final__` arrives.

```bash
curl -N -X POST https://fitness-coach-production-742e.up.railway.app/api/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"What muscles does a deadlift work?"}'
```
