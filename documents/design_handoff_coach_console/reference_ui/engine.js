/* engine.js — fake multi-agent backend for the mock.
   Exposes window.FitEngine with:
     - EXERCISES: a small but realistic slice of exercises.json
     - route(text, threshold): returns a turn object the UI renders
   No real LLM is called; responses are scripted but the routing/confidence
   logic is honest about how the real system would behave. */
(function () {
  "use strict";

  // ---- Exercise dataset (slice of the 50-row exercises.json) -------------
  // Fields mirror the assessment: muscle_groups, joints_loaded,
  // movement_patterns, equipment_required, priority_tier, is_bilateral,
  // bilateral_pair_id.
  const EXERCISES = [
    { id: "ex_back_squat", name: "Barbell Back Squat", muscle_groups: ["quads", "glutes", "core"], joints_loaded: ["knee", "hip", "lumbar"], movement_patterns: ["squat"], equipment_required: ["barbell", "rack"], priority_tier: 1, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_deadlift", name: "Conventional Deadlift", muscle_groups: ["hamstrings", "glutes", "back", "core"], joints_loaded: ["hip", "knee", "lumbar"], movement_patterns: ["hinge"], equipment_required: ["barbell"], priority_tier: 1, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_bench", name: "Barbell Flat Bench Press", muscle_groups: ["chest", "shoulders", "triceps"], joints_loaded: ["shoulder", "elbow"], movement_patterns: ["horizontal_push"], equipment_required: ["barbell", "bench"], priority_tier: 1, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_db_bench", name: "Dumbbell Bench Press", muscle_groups: ["chest", "shoulders", "triceps"], joints_loaded: ["shoulder", "elbow"], movement_patterns: ["horizontal_push"], equipment_required: ["dumbbell", "bench"], priority_tier: 1, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_db_row", name: "One-Arm Dumbbell Row", muscle_groups: ["back", "biceps"], joints_loaded: ["shoulder", "elbow"], movement_patterns: ["horizontal_pull"], equipment_required: ["dumbbell", "bench"], priority_tier: 1, is_bilateral: false, bilateral_pair_id: "ex_db_row" },
    { id: "ex_db_ohp", name: "Seated Dumbbell Shoulder Press", muscle_groups: ["shoulders", "triceps"], joints_loaded: ["shoulder", "elbow"], movement_patterns: ["vertical_push"], equipment_required: ["dumbbell", "bench"], priority_tier: 2, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_db_curl", name: "Dumbbell Biceps Curl", muscle_groups: ["biceps"], joints_loaded: ["elbow"], movement_patterns: ["elbow_flexion"], equipment_required: ["dumbbell"], priority_tier: 3, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_db_lateral", name: "Dumbbell Lateral Raise", muscle_groups: ["shoulders"], joints_loaded: ["shoulder"], movement_patterns: ["shoulder_abduction"], equipment_required: ["dumbbell"], priority_tier: 3, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_db_tri", name: "Dumbbell Overhead Triceps Extension", muscle_groups: ["triceps"], joints_loaded: ["elbow", "shoulder"], movement_patterns: ["elbow_extension"], equipment_required: ["dumbbell"], priority_tier: 3, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_pushup", name: "Push-Up", muscle_groups: ["chest", "shoulders", "triceps", "core"], joints_loaded: ["shoulder", "elbow"], movement_patterns: ["horizontal_push"], equipment_required: ["bodyweight"], priority_tier: 2, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_pullup", name: "Pull-Up", muscle_groups: ["back", "biceps"], joints_loaded: ["shoulder", "elbow"], movement_patterns: ["vertical_pull"], equipment_required: ["pullup_bar"], priority_tier: 1, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_cable_row", name: "Seated Cable Row", muscle_groups: ["back", "biceps"], joints_loaded: ["shoulder", "elbow"], movement_patterns: ["horizontal_pull"], equipment_required: ["cable"], priority_tier: 2, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_lat_pulldown", name: "Lat Pulldown", muscle_groups: ["back", "biceps"], joints_loaded: ["shoulder", "elbow"], movement_patterns: ["vertical_pull"], equipment_required: ["cable"], priority_tier: 2, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_walking_lunge", name: "Walking Lunge", muscle_groups: ["quads", "glutes"], joints_loaded: ["knee", "hip"], movement_patterns: ["lunge"], equipment_required: ["dumbbell"], priority_tier: 2, is_bilateral: false, bilateral_pair_id: "ex_walking_lunge" },
    { id: "ex_rdl", name: "Dumbbell Romanian Deadlift", muscle_groups: ["hamstrings", "glutes"], joints_loaded: ["hip", "lumbar"], movement_patterns: ["hinge"], equipment_required: ["dumbbell"], priority_tier: 2, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_plank", name: "Front Plank", muscle_groups: ["core"], joints_loaded: ["shoulder"], movement_patterns: ["anti_extension"], equipment_required: ["bodyweight"], priority_tier: 3, is_bilateral: true, bilateral_pair_id: null },
    // warmup / mobility
    { id: "ex_arm_circles", name: "Arm Circles", muscle_groups: ["shoulders"], joints_loaded: ["shoulder"], movement_patterns: ["mobility"], equipment_required: ["bodyweight"], priority_tier: 4, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_band_pullapart", name: "Band Pull-Apart", muscle_groups: ["shoulders", "back"], joints_loaded: ["shoulder"], movement_patterns: ["mobility"], equipment_required: ["band"], priority_tier: 4, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_catcow", name: "Cat-Cow", muscle_groups: ["core", "back"], joints_loaded: ["lumbar"], movement_patterns: ["mobility"], equipment_required: ["bodyweight"], priority_tier: 4, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_doorway_stretch", name: "Doorway Chest Stretch", muscle_groups: ["chest"], joints_loaded: ["shoulder"], movement_patterns: ["stretch"], equipment_required: ["bodyweight"], priority_tier: 4, is_bilateral: true, bilateral_pair_id: null },
    { id: "ex_child_pose", name: "Child's Pose", muscle_groups: ["back"], joints_loaded: ["lumbar"], movement_patterns: ["stretch"], equipment_required: ["bodyweight"], priority_tier: 4, is_bilateral: true, bilateral_pair_id: null }
  ];

  const byId = Object.fromEntries(EXERCISES.map((e) => [e.id, e]));

  // ---- scripted turns -----------------------------------------------------
  // Each builder returns the assistant payload + the trace (ordered events).
  // intrinsicConfidence is what the router would emit; the UI compares it to
  // the live threshold and downgrades to CLARIFY when it falls short.

  function coachDeadlift() {
    return {
      route: "COACH",
      confidence: 0.96,
      rationale: "Informational 'what muscles' question about a named lift. No logging verbs, no generation request. Clear COACH.",
      trace: [
        { kind: "router", label: "route_query", detail: "structured_output → RoutingDecision", out: "COACH · 0.96" },
        { kind: "tool", label: "lookup_exercise", input: { query: "deadlift" }, out: "1 match · Conventional Deadlift", count: 1 },
        { kind: "agent", label: "coach_agent", out: "answer composed from exercise metadata" }
      ],
      content: {
        type: "coach",
        prose: "The conventional deadlift is a hip-hinge, so the prime movers are your posterior chain: the hamstrings and glutes drive hip extension while the erectors and lats keep the spine braced and the bar tight to the body. The quads contribute off the floor, and your grip, traps, and core all work isometrically to stabilize the load.",
        joints: ["hip", "knee", "lumbar"],
        refs: ["ex_deadlift"]
      }
    };
  }

  function generateUpperDumbbell() {
    const warmup = ["ex_arm_circles", "ex_band_pullapart"];
    const main = ["ex_db_bench", "ex_db_row", "ex_db_ohp", "ex_db_curl", "ex_db_tri"];
    const cooldown = ["ex_doorway_stretch", "ex_child_pose"];
    return {
      route: "WORKOUT_GENERATE",
      confidence: 0.93,
      rationale: "Explicit build request with constraints (30 min, upper body, dumbbells). Maps cleanly to the generator's tool loop.",
      trace: [
        { kind: "router", label: "route_query", detail: "structured_output → RoutingDecision", out: "WORKOUT_GENERATE · 0.93" },
        { kind: "tool", label: "search_exercises", input: { muscle_groups: ["chest", "back", "shoulders", "arms"], equipment_required: ["dumbbell"], time_budget_min: 30 }, out: "9 results", count: 9 },
        { kind: "tool", label: "build_workout", input: { warmup: 2, main: 5, cooldown: 2, target_min: 30 }, out: "ok · est. 29 min" },
        { kind: "note", label: "constraint", out: "all main lifts bilateral — no unilateral pairing needed" }
      ],
      content: {
        type: "workout",
        title: "30-min Upper Body · Dumbbells",
        meta: { duration: "≈29 min", equipment: ["dumbbell", "bench"], focus: "Chest · Back · Shoulders · Arms" },
        sections: [
          { name: "Warm-up", items: warmup.map((id) => ({ id, sets: 1, reps: "30s", rest: "—" })) },
          { name: "Main", items: [
            { id: "ex_db_bench", sets: 4, reps: "8–10", rest: "90s" },
            { id: "ex_db_row", sets: 4, reps: "10 / side", rest: "90s" },
            { id: "ex_db_ohp", sets: 3, reps: "10–12", rest: "75s" },
            { id: "ex_db_curl", sets: 3, reps: "12", rest: "60s" },
            { id: "ex_db_tri", sets: 3, reps: "12", rest: "60s" }
          ] },
          { name: "Cool-down", items: cooldown.map((id) => ({ id, sets: 1, reps: "45s", rest: "—" })) }
        ]
      }
    };
  }

  function logBench() {
    return {
      route: "WORKOUT_LOG",
      confidence: 0.89,
      rationale: "Past-tense completion ('I just did') with explicit sets×reps×weight. Logging intent, not a question.",
      trace: [
        { kind: "router", label: "route_query", detail: "structured_output → RoutingDecision", out: "WORKOUT_LOG · 0.89" },
        { kind: "tool", label: "parse_log", input: { utterance: "3x10 bench press at 185 lbs" }, out: "1 entry parsed" },
        { kind: "tool", label: "fuzzy_match", input: { query: "bench press" }, out: "Barbell Flat Bench Press · 0.82", count: 1 },
        { kind: "agent", label: "logger_agent", out: "entry committed to thread state" }
      ],
      content: {
        type: "log",
        entries: [
          { raw: "bench press", matched_id: "ex_bench", score: 0.82, sets: 3, reps: 10, weight: 185, unit: "lb" }
        ]
      }
    };
  }

  function resilienceRowingMachine() {
    return {
      route: "WORKOUT_GENERATE",
      confidence: 0.9,
      rationale: "Build request, but the requested equipment ('rowing machine') is absent from the dataset — generator must recover.",
      trace: [
        { kind: "router", label: "route_query", detail: "structured_output → RoutingDecision", out: "WORKOUT_GENERATE · 0.90" },
        { kind: "tool", label: "search_exercises", input: { muscle_groups: ["back"], equipment_required: ["rowing_machine"] }, out: "0 results", count: 0 },
        { kind: "recover", label: "fallback", out: "0 results → drop unavailable equipment, re-search by movement_pattern=horizontal_pull / vertical_pull" },
        { kind: "tool", label: "search_exercises", input: { muscle_groups: ["back"], movement_patterns: ["horizontal_pull", "vertical_pull"] }, out: "3 results", count: 3 },
        { kind: "tool", label: "build_workout", input: { main: 3 }, out: "ok · substituted" }
      ],
      content: {
        type: "workout",
        title: "Back Session · closest available equipment",
        recovered: "No “rowing machine” in the exercise library — I didn't invent one. I substituted the nearest available horizontal/vertical pulls.",
        meta: { duration: "≈25 min", equipment: ["cable", "dumbbell"], focus: "Back" },
        sections: [
          { name: "Main", items: [
            { id: "ex_cable_row", sets: 4, reps: "10–12", rest: "75s" },
            { id: "ex_db_row", sets: 3, reps: "10 / side", rest: "75s" },
            { id: "ex_lat_pulldown", sets: 3, reps: "12", rest: "60s" }
          ] }
        ]
      }
    };
  }

  // ambiguous prompts → low intrinsic confidence, candidate distribution
  function ambiguousAdjust() {
    return {
      route: "WORKOUT_LOG",
      confidence: 0.41,
      rationale: "Past-tense ('did a workout yesterday') leans LOG, but 'adjust it' implies GENERATE. No structured data to log. Genuinely mixed.",
      candidates: [
        { route: "WORKOUT_LOG", p: 0.41 },
        { route: "WORKOUT_GENERATE", p: 0.34 },
        { route: "COACH", p: 0.25 }
      ],
      trace: [
        { kind: "router", label: "route_query", detail: "structured_output → RoutingDecision", out: "top: WORKOUT_LOG · 0.41" },
        { kind: "note", label: "candidates", out: "LOG 0.41 · GEN 0.34 · COACH 0.25" }
      ],
      content: {
        type: "clarify",
        question: "Want me to log yesterday's workout, or build you an adjusted version of it?",
        options: ["Log what I did", "Build an adjusted version", "Just coaching advice"]
      }
    };
  }

  function ambiguousBench() {
    return {
      route: "COACH",
      confidence: 0.36,
      rationale: "Two words, no verb. Could be a coaching question, a log fragment, or a generation seed. Insufficient signal.",
      candidates: [
        { route: "COACH", p: 0.36 },
        { route: "WORKOUT_LOG", p: 0.33 },
        { route: "WORKOUT_GENERATE", p: 0.31 }
      ],
      trace: [
        { kind: "router", label: "route_query", detail: "structured_output → RoutingDecision", out: "top: COACH · 0.36" },
        { kind: "note", label: "candidates", out: "COACH 0.36 · LOG 0.33 · GEN 0.31" }
      ],
      content: {
        type: "clarify",
        question: "“Bench press” — what would you like to do with it?",
        options: ["Tell me about it", "Log a bench set", "Add it to a workout"]
      }
    };
  }

  // generic fallback for free-typed text we don't recognize
  function genericCoach(text) {
    const conf = 0.62;
    return {
      route: "COACH",
      confidence: conf,
      rationale: "No logging data and no explicit build request detected — defaulting to the COACH agent for a conversational answer.",
      trace: [
        { kind: "router", label: "route_query", detail: "structured_output → RoutingDecision", out: "COACH · " + conf.toFixed(2) },
        { kind: "agent", label: "coach_agent", out: "free-form answer" }
      ],
      content: {
        type: "coach",
        prose: "That's a coaching-style question. In the real system this routes to the COACH agent, which answers from exercise metadata and general training principles. (This mock only scripts a handful of canned prompts — try one of the example chips on the left for the rich, route-specific output.)",
        joints: [],
        refs: []
      }
    };
  }

  // map a user utterance to one of the scripted builders.
  // Order matters: specific / ambiguous cases are tested before the broad
  // coach matcher so "workout" doesn't get swallowed by /work/.
  const SCENARIOS = [
    { test: (t) => /rowing machine|rower|sled|equipment .*not/.test(t), make: resilienceRowingMachine, key: "resilience" },
    { test: (t) => /adjust|yesterday/.test(t), make: ambiguousAdjust, key: "ambiguous-adjust" },
    { test: (t) => /^\s*bench press\s*[.!?]*\s*$/.test(t), make: ambiguousBench, key: "ambiguous-bench" },
    { test: (t) => /(\d+\s*x\s*\d+)|just did|logged|did .*(bench|squat|press|deadlift|curl)|@\s*\d|\d+\s*(lb|lbs|kg)/.test(t), make: logBench, key: "log" },
    { test: (t) => /build|generate|program|put together|give me a/.test(t) && /workout|session|upper|lower|body|dumbbell|leg|push|pull/.test(t), make: generateUpperDumbbell, key: "generate" },
    { test: (t) => /muscle|what.*(work|do)|how.*(work|target)|which muscle/.test(t), make: coachDeadlift, key: "coach" }
  ];

  function classify(text) {
    const t = (text || "").toLowerCase();
    for (const s of SCENARIOS) {
      try { if (s.test(t)) return s.make(text); } catch (e) {}
    }
    return genericCoach(text);
  }

  // public: route() applies the live confidence threshold and may downgrade
  // a confident scripted route into a CLARIFY turn.
  function route(text, threshold) {
    const base = classify(text);
    const thr = typeof threshold === "number" ? threshold : 0.6;
    const isClarifyContent = base.content && base.content.type === "clarify";

    if (base.confidence < thr && !isClarifyContent) {
      // downgrade: confident enough to guess, not confident enough to act
      return {
        route: "CLARIFY",
        confidence: base.confidence,
        downgradedFrom: base.route,
        threshold: thr,
        rationale: "Top route " + base.route + " scored " + base.confidence.toFixed(2) + ", below the " + thr.toFixed(2) + " threshold. Asking instead of guessing.",
        trace: [
          ...(base.trace ? base.trace.slice(0, 1) : []),
          { kind: "note", label: "gate", out: base.confidence.toFixed(2) + " < threshold " + thr.toFixed(2) + " → CLARIFY" }
        ],
        content: {
          type: "clarify",
          question: "I'm only " + Math.round(base.confidence * 100) + "% sure I read that right — did you want me to " + verb(base.route) + "?",
          options: routeOptions(base.route)
        }
      };
    }
    // clarify-by-nature turns: surface as CLARIFY for display/theming, but
    // keep the top candidate visible in the trace as `downgradedFrom`.
    if (isClarifyContent) {
      return Object.assign({}, base, {
        route: "CLARIFY",
        downgradedFrom: base.route !== "CLARIFY" ? base.route : base.downgradedFrom,
        threshold: thr
      });
    }
    return Object.assign({ threshold: thr }, base);
  }

  function verb(r) {
    return r === "COACH" ? "answer it as a coaching question"
      : r === "WORKOUT_GENERATE" ? "build you a workout"
      : r === "WORKOUT_LOG" ? "log that as a completed set"
      : "help";
  }
  function routeOptions(r) {
    const all = {
      COACH: "Answer as coaching",
      WORKOUT_GENERATE: "Build a workout",
      WORKOUT_LOG: "Log a set"
    };
    const top = all[r];
    const rest = Object.keys(all).filter((k) => k !== r).map((k) => all[k]);
    return [top, ...rest].filter(Boolean);
  }

  window.FitEngine = { EXERCISES, byId, route, classify };
})();
