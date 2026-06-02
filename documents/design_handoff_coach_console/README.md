# Handoff: Fitness Coaching · Multi-Agent Console (web view)

This bundle is the **UI design reference** for the take-home's "simple web view." It pairs
with the backend task (LangGraph hub + 3 sub-agents) by defining exactly what the frontend
renders and — importantly — **the JSON contract the backend must emit** for each turn.

> ⚠️ The files in `reference_ui/` are a **design reference built in HTML/React**, not
> production code to ship as-is. They show intended look + behavior. Recreate them in your
> chosen web view (Streamlit, FastAPI+HTML, etc.), or reuse the HTML directly per **Option B**
> below. `engine.js` is a **mock backend** — its scripted responses get replaced by real
> graph output, but the *shape* it returns is the contract to preserve.

---

## How to use this with Claude Code

1. Copy the `design_handoff_coach_console/` folder into your repo root.
2. In Claude Code, start with:
   > "Read `design_handoff_coach_console/README.md` and the files in `reference_ui/`. We're
   > building the web view described there on top of our LangGraph system. Follow **Option A**
   > (rebuild in Streamlit) — match the layout, cards, and trace exactly."
3. Point it at your real graph code so it wires the contract (below) to actual agent output.

### Two integration paths

**Option A — Design spec (rebuild in Streamlit).** Treat `reference_ui/` as the pixel
reference. Recreate the three regions with `st.sidebar`, `st.chat_message`, custom
HTML/CSS via `st.markdown(..., unsafe_allow_html=True)` for the cards, and `st.expander`
for "Show reasoning." Use the **Design Tokens** and **Screen spec** sections to match it.

**Option B — Use the HTML as the real frontend (recommended if you want it to look like
this).** The React app already renders every card + the trace. Replace the body of
`route(text, threshold)` in `engine.js` with a `fetch('/route', {...})` call to a FastAPI
endpoint that runs your compiled LangGraph hub and returns the **same JSON shape**. Nothing
in `components.jsx`/`app.jsx` needs to change. This is the fastest way to a polished demo.

---

## The UI ⇄ backend contract (most important section)

Every assistant turn is one object. `app.jsx` calls `FitEngine.route(text, threshold)` and
renders whatever comes back. Your backend (`/route`) must return this shape:

```jsonc
{
  "route": "COACH" | "WORKOUT_GENERATE" | "WORKOUT_LOG" | "CLARIFY",
  "confidence": 0.0–1.0,                 // from the router's structured output
  "rationale": "one sentence",           // why this route (shown in trace)
  "downgradedFrom": "WORKOUT_LOG",        // optional: original top route if gated/ambiguous
  "candidates": [                          // optional: full distribution for ambiguous turns
    { "route": "WORKOUT_LOG", "p": 0.41 },
    { "route": "WORKOUT_GENERATE", "p": 0.34 }
  ],
  "threshold": 0.60,                       // the confidence floor in effect this turn
  "trace": [                               // ordered events → the "Show reasoning" timeline
    { "kind": "router", "label": "route_query", "detail": "structured_output → RoutingDecision", "out": "WORKOUT_GENERATE · 0.93" },
    { "kind": "tool",   "label": "search_exercises", "input": { "muscle_groups": ["chest"], "equipment_required": ["dumbbell"] }, "out": "9 results", "count": 9 },
    { "kind": "recover","label": "fallback", "out": "0 results → re-search by movement_pattern" },
    { "kind": "agent",  "label": "logger_agent", "out": "entry committed to thread state" },
    { "kind": "note",   "label": "candidates", "out": "LOG 0.41 · GEN 0.34" }
  ],
  "content": { /* one of the four card payloads below */ }
}
```

**`trace[].kind`** drives the colored dot + tag in the timeline:
`router` (indigo) · `tool` (green) · `recover` (red — resilience events) · `agent` (blue) · `note` (gray).
Set `"count": 0` on a tool step to render the "0 results" recovery flag in red.

### `content` payloads, one per route

```jsonc
// COACH — prose answer + referenced exercises
{ "type": "coach", "prose": "…", "joints": ["hip","knee"], "refs": ["ex_deadlift"] }

// WORKOUT_GENERATE — structured workout
{ "type": "workout", "title": "30-min Upper Body · Dumbbells",
  "recovered": "optional red banner text when equipment was substituted",
  "meta": { "duration": "≈29 min", "equipment": ["dumbbell","bench"], "focus": "Chest · Back · Arms" },
  "sections": [
    { "name": "Warm-up", "items": [ { "id": "ex_arm_circles", "sets": 1, "reps": "30s", "rest": "—" } ] },
    { "name": "Main",    "items": [ { "id": "ex_db_bench", "sets": 4, "reps": "8–10", "rest": "90s" } ] }
  ] }

// WORKOUT_LOG — parsed log entries with fuzzy match made visible
{ "type": "log", "entries": [
  { "raw": "bench press", "matched_id": "ex_bench", "score": 0.82, "sets": 3, "reps": 10, "weight": 185, "unit": "lb" }
] }

// CLARIFY — disambiguation question + candidate buttons
{ "type": "clarify", "question": "…?", "options": ["Log what I did", "Build an adjusted version"] }
```

`item.id` / `matched_id` reference rows in your real `exercises.json` by `id`; the UI looks
up the display name, `equipment_required`, `priority_tier`, and `is_bilateral` from that
dataset (see `engine.js` `EXERCISES`, which is a 20-row stand-in — swap in the real 50).

### Two backend behaviors the UI expects you to implement
- **Confidence gating:** if `confidence < threshold` and the turn isn't already a clarify,
  return `route: "CLARIFY"` with `downgradedFrom` set to the would-be route. (The sidebar
  slider sends `threshold`; reviewers drag it up to watch this fire.)
- **Ambiguous-by-nature turns:** when the router itself is split, return `route: "CLARIFY"`
  with the full `candidates` distribution and `downgradedFrom` = top candidate.

---

## Fidelity

**High-fidelity.** Final colors, type, spacing, and interactions are all specified below and
in `reference_ui/`. Match it closely.

## Screens / Views

**One screen, three regions** (desktop, fills viewport; sidebar hides < 860px wide).
Grid: `312px | 1fr`.

### Region 1 — Sidebar (`312px`, bg `--sidebar`, right border `--border`)
Top to bottom:
- **Brand row** — 30px gradient mark (dumbbell icon) + "Coach Console" / mono subtitle
  "langgraph · hub + 3 agents".
- **Configuration** group: Model `<select>`; **Confidence threshold** slider (0–1, step .01,
  value shown in mono accent) with hint "Routes scoring below this fall back to a CLARIFY
  question."; full-width **New conversation** button (resets thread + clears messages, new
  `thr_xxxxxx` id).
- **Example prompts** — 6 left-aligned chips, each: colored dot + text + mono route tag.
  One per route + 2 ambiguous + 1 resilience (see `EXAMPLES` in `app.jsx`). Clicking sends it.
- **Session log** — accumulates every `WORKOUT_LOG` entry across the thread as rows
  `name · sets×reps · weight`. Empty state is a dashed placeholder. New rows flash amber once.
  (This reads off checkpointed state → doubles as proof memory works.)

### Region 2 — Chat (main column, max-width 760px, centered)
- **Top bar** (54px): route icon + "Fitness Coaching · Multi-Agent Hub" + mono thread pill;
  right side = legend of the 4 route colors.
- **Transcript** of turns:
  - **User** → dark right-aligned bubble (`--user-bubble`), max-width 78%.
  - **Assistant** → header row [route avatar + agent-name badge + `conf 0.xx`], then a
    **route-themed card** (3px top border in the route color), then the **trace expander**.
    The header, avatar, and card border **must all use the same route color** (a CLARIFY turn
    is violet throughout — including its "Hub Router" badge).
- **Typing indicator** while "routing → <agent>…" (bouncing dots in route color).
- **Composer** (bottom, sticky over a fade): auto-growing textarea, Enter to send,
  Shift+Enter newline, round accent send button; mono hint line showing model · threshold.

### Region 3 — Trace ("Show reasoning", inline under each assistant turn)
Collapsed by default. Toggle row: chevron + brain icon + "Show reasoning · <route> · <conf>",
plus a red "recovered" flag when the trace contains a recovery/0-results step. Expanded panel:
- **Meta block**: route badge; confidence bar + `conf / thr`; candidate distribution (if any);
  italic rationale.
- **Timeline**: vertical rail of steps, each = colored dot + mono label + kind tag + I/O
  (`input → out`), rendering `JsonInline` for tool inputs. Recovery steps render red.

## Interactions & Behavior
- Send (button / Enter / example chip / clarify option) → append user msg → show typing
  indicator colored by the predicted route → after 560–1040ms append the assistant turn.
- **Clarify option buttons** map to concrete follow-up prompts (see `onPickClarify` in
  `app.jsx`) and re-send.
- **Threshold slider** is live: re-routes at send time; raising it past a turn's confidence
  forces CLARIFY.
- **New conversation** clears transcript + issues a new thread id → empty state shows.
- Autoscroll: jump to latest on load; smooth-follow only if already near the bottom.
- Entrance animations are **transform-only** (never opacity) and gated on
  `prefers-reduced-motion: no-preference`, so content is always visible if animation is off.
- Tweaks panel (host-toggled): theme light/dark, accent color, density, color-code routes
  on/off, auto-open reasoning. Optional — drop it if your stack has no equivalent.

## State Management
- `messages: [{id, role:'user'|'assistant', text? , turn?}]`
- `thread` id (string), `threshold` (0–1), `model` (string), `draft`, `thinking` ({route} | null)
- `sessionLog` is **derived** from `messages` (all `content.type==='log'` entries) — not stored
  separately. In the real app it reads from the LangGraph checkpointer state for `thread_id`.

## Design Tokens

Fonts: **IBM Plex Sans** (UI) + **IBM Plex Mono** (routes, IDs, numbers, trace, code).

Light theme: `--bg #f4f5f8` · `--surface #fff` · `--surface-2 #f7f8fa` · `--surface-3 #eef0f4`
· `--sidebar #fbfbfd` · `--border #e6e8ee` · `--border-strong #d6dae2` · `--text #1b2330`
· `--text-2 #5a6675` · `--text-3 #8e98a8`. (Dark theme tokens are in `index.html` `:root[data-theme="dark"]`.)

Accent (default): `#5b5bd6` (presets: `#0d9488`, `#e2603b`, `#2f6fed`).

Route palette (color / bg / ring):
- COACH `#0284c7` / `#e6f4fb` / `#bae6fd`
- WORKOUT_GENERATE `#059669` / `#e3f6ee` / `#a7f3d0`
- WORKOUT_LOG `#d97706` / `#fdf1dc` / `#fde3b3`
- CLARIFY `#7c3aed` / `#f1ebfd` / `#ddd0fb`
- recover/error `#dc2626` / `#fdeaea` / `#f7c9c9`

Radius: 12 (card) / 8 (sm) / 16 (lg). Shadows + full token set live in `index.html` `<style>`.

## Assets
No external images. All icons are inline SVG in `components.jsx` (`Icons`). Fonts load from
Google Fonts. No brand assets — fully original.

## Files (`reference_ui/`)
- `index.html` — shell, all CSS design tokens + component styles, script wiring.
- `engine.js` — **mock backend** + 20-row exercise stand-in. Replace with real graph output;
  preserve the return shape (the contract above).
- `components.jsx` — icons, route theming, the 4 cards, the trace expander.
- `app.jsx` — state, sidebar, chat, composer, session log, send/route flow, tweaks.
- `tweaks-panel.jsx` — optional tweak-panel host wiring (skip in non-HTML stacks).
