/* app.jsx — wires the console to the FastAPI backend. */
const { useState, useEffect, useRef, useCallback } = React;

const MODELS = [
  "anthropic/claude-3.5-sonnet",
  "openai/gpt-4o",
  "openai/gpt-4o-mini",
  "google/gemini-1.5-pro",
  "meta-llama/llama-3.1-70b",
];

const EXAMPLES = [
  { text: "What muscles does a deadlift work?", tag: "COACH", color: "var(--r-coach)" },
  { text: "Build me a 30 min upper body session with dumbbells", tag: "GENERATE", color: "var(--r-generate)" },
  { text: "I just did 3x10 bench press at 185 lbs", tag: "LOG", color: "var(--r-log)" },
  { text: "I did a workout yesterday, can you adjust it?", tag: "AMBIGUOUS", color: "var(--r-clarify)" },
  { text: "Bench press", tag: "AMBIGUOUS", color: "var(--r-clarify)" },
  { text: "Build me a back workout using a rowing machine", tag: "RESILIENCE", color: "var(--r-recover)" },
  { text: "Build a leg workout but avoid loading my shoulder", tag: "INJURY", color: "var(--r-generate)" },
];

const ACCENTS = {
  "#5b5bd6": { soft: "#ecedfb", ring: "rgba(91,91,214,.28)", press: "#4a4ab8" },
  "#0d9488": { soft: "#dcf3f0", ring: "rgba(13,148,136,.26)", press: "#0b7a70" },
  "#e2603b": { soft: "#fdeae3", ring: "rgba(226,96,59,.26)", press: "#c44f2e" },
  "#2f6fed": { soft: "#e4edfe", ring: "rgba(47,111,237,.26)", press: "#245ccc" },
};

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#5b5bd6",
  "density": "comfortable",
  "theme": "light",
  "routeColors": true,
  "autoOpenTrace": false
}/*EDITMODE-END*/;

let TURN_ID = 0;
function nid() { return "t" + (++TURN_ID); }

function deriveSessionLog(messages) {
  const out = [];
  messages.forEach((m) => {
    if (m.role === "assistant" && m.turn && m.turn.content && m.turn.content.type === "log") {
      m.turn.content.entries.forEach((e) => {
        const ex = window.FitEngine.byId[e.matched_id];
        const name = ex ? ex.name : (e.matched_name || e.raw || e.matched_id || "—");
        const sr = (e.sets != null && e.reps != null) ? `${e.sets}×${e.reps}` : "";
        const w = e.weight != null ? `${e.weight}${e.unit || ""}` : "";
        out.push({ name, sr, w });
      });
    }
  });
  return out;
}

function newThreadId() {
  return "thr_" + Math.random().toString(36).slice(2, 8);
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [model, setModel] = useState(MODELS[0]);
  const [threshold, setThreshold] = useState(0.6);
  const [messages, setMessages] = useState([]);
  const [thread, setThread] = useState(newThreadId);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const scrollRef = useRef(null);
  const taRef = useRef(null);
  const flashIdx = useRef(-1);
  const firstScroll = useRef(true);

  useEffect(() => {
    const html = document.documentElement;
    html.setAttribute("data-theme", t.theme);
    html.setAttribute("data-density", t.density);
    html.setAttribute("data-routecolors", t.routeColors ? "on" : "off");
    const a = ACCENTS[t.accent] || ACCENTS["#5b5bd6"];
    html.style.setProperty("--accent", t.accent);
    html.style.setProperty("--accent-soft", a.soft);
    html.style.setProperty("--accent-ring", a.ring);
    html.style.setProperty("--accent-press", a.press);
  }, [t.theme, t.density, t.routeColors, t.accent]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (firstScroll.current) {
      firstScroll.current = false;
      el.scrollTop = el.scrollHeight;
      return;
    }
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 260;
    if (atBottom || thinking) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages.length, thinking]);

  const sessionLog = deriveSessionLog(messages);

  const send = useCallback(async (rawText) => {
    const text = (rawText != null ? rawText : draft).trim();
    if (!text || thinking) return;
    setDraft("");
    if (taRef.current) taRef.current.style.height = "auto";

    const userMsg = { id: nid(), role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setThinking(true);

    const placeholderId = nid();
    const partialTurn = {
      route: "CLARIFY",
      confidence: 0,
      rationale: "",
      threshold,
      trace: [],
      content: { type: "coach", prose: "Routing…", joints: [], refs: [] },
      streaming: true,
    };

    const applyPartial = (ev) => {
      if (ev.node === "__thread__" && ev.thread_id) {
        setThread(ev.thread_id);
        return;
      }
      const upd = ev.update || {};
      if (upd.route) partialTurn.route = upd.route;
      if (upd.confidence != null) partialTurn.confidence = upd.confidence;
      if (upd.routing_rationale) partialTurn.rationale = upd.routing_rationale;
      if (upd.trace && upd.trace.length) {
        partialTurn.trace = partialTurn.trace.concat(upd.trace);
      }
      if (ev.node && ev.node !== "__final__") {
        partialTurn.content = {
          type: "coach",
          prose: `Running ${ev.node}…`,
          joints: [],
          refs: [],
        };
      }
      setMessages((prev) => {
        const has = prev.some((m) => m.id === placeholderId);
        const row = { id: placeholderId, role: "assistant", turn: { ...partialTurn } };
        if (has) return prev.map((m) => (m.id === placeholderId ? row : m));
        return [...prev, row];
      });
    };

    try {
      let turn;
      if (window.FitEngine.routeStream) {
        setMessages((prev) => [...prev, { id: placeholderId, role: "assistant", turn: { ...partialTurn } }]);
        turn = await window.FitEngine.routeStream(text, threshold, thread, applyPartial);
      } else {
        turn = await window.FitEngine.route(text, threshold, thread);
      }
      if (turn.thread_id && turn.thread_id !== thread) {
        setThread(turn.thread_id);
      }
      if (turn.content && turn.content.type === "log") {
        flashIdx.current = sessionLog.length;
      }
      setMessages((prev) => {
        const without = prev.filter((m) => m.id !== placeholderId);
        return [...without, { id: nid(), role: "assistant", turn }];
      });
    } catch (e) {
      try {
        const turn = await window.FitEngine.route(text, threshold, thread);
        setMessages((prev) => {
          const without = prev.filter((m) => m.id !== placeholderId);
          return [...without, { id: nid(), role: "assistant", turn }];
        });
      } catch (e2) {
        setMessages((prev) => {
          const without = prev.filter((m) => m.id !== placeholderId);
          return [...without, {
            id: nid(),
            role: "assistant",
            turn: {
              route: "CLARIFY",
              confidence: 0,
              rationale: "request failed",
              threshold,
              trace: [],
              content: { type: "clarify", question: "Request failed: " + (e2.message || e2), options: [] },
            },
          }];
        });
      }
    } finally {
      setThinking(false);
    }
  }, [draft, thinking, threshold, thread, sessionLog.length]);

  const onPickClarify = useCallback((option) => {
    const map = {
      "Log what I did": "I did 3x10 bench press at 185 lbs",
      "Build an adjusted version": "Build me a 30 min upper body session with dumbbells",
      "Just coaching advice": "What muscles does a deadlift work?",
      "Tell me about it": "What muscles does a bench press work?",
      "Log a bench set": "I just did 3x10 bench press at 185 lbs",
      "Add it to a workout": "Build me a 30 min upper body session with dumbbells",
      "Build a workout": "Build me a 30 min upper body session with dumbbells",
      "Log a set": "I just did 3x10 bench press at 185 lbs",
      "Answer as coaching": "What muscles does a deadlift work?",
    };
    send(map[option] || option);
  }, [send]);

  const resetThread = () => {
    setMessages([]);
    setThread(newThreadId());
    setThinking(false);
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };
  const onInput = (e) => {
    setDraft(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px";
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">{Icons.dumbbell}</div>
          <div>
            <div className="brand-name">Coach Console</div>
            <div className="brand-sub">langgraph · hub + 3 agents</div>
          </div>
        </div>
        <div className="sidebar-scroll">
          <div className="side-group">
            <div className="side-label">{Icons.gear}<span style={{ marginRight: "auto", marginLeft: 6 }}>Configuration</span></div>
            <div className="field-row">
              <span className="field-name">Model</span>
              <select className="select" value={model} onChange={(e) => setModel(e.target.value)}>
                {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div className="field-row">
              <div className="thr-head">
                <span className="field-name">Confidence threshold</span>
                <span className="thr-val">{threshold.toFixed(2)}</span>
              </div>
              <input className="slider" type="range" min="0" max="1" step="0.01"
                value={threshold} onChange={(e) => setThreshold(parseFloat(e.target.value))} />
              <span className="thr-hint">Routes scoring below this fall back to a CLARIFY question. Drag up to watch it trigger.</span>
            </div>
            <button className="btn btn-block" onClick={resetThread} style={{ marginTop: 2 }}>
              {Icons.reset} New conversation
            </button>
          </div>

          <div className="side-group">
            <div className="side-label"><span>Example prompts</span></div>
            <div className="examples">
              {EXAMPLES.map((ex) => (
                <button key={ex.text} className="example" style={{ "--ex-color": ex.color }} onClick={() => send(ex.text)}>
                  <span className="dot" />
                  <span className="ex-text">{ex.text}</span>
                  <span className="ex-tag">{ex.tag}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="side-group">
            <div className="side-label">{Icons.layers}<span style={{ marginRight: "auto", marginLeft: 6 }}>Session log</span><span style={{ color: "var(--text-3)" }}>{sessionLog.length}</span></div>
            {sessionLog.length === 0 ? (
              <div className="log-empty">No sets logged yet. Try “I did 3×10 bench press at 185 lbs”.</div>
            ) : (
              <div className="log-table">
                {sessionLog.map((r, i) => (
                  <div className={"log-row" + (i === flashIdx.current ? " log-flash" : "")} key={i}>
                    <span className="lx-name">{r.name}</span>
                    <span className="lx-sr">{r.sr}</span>
                    <span className="lx-w">{r.w}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="topbar-title">
            {Icons.route}
            <span>Fitness Coaching · Multi-Agent Hub</span>
            <span className="thread-pill">{thread}</span>
          </div>
          <div className="topbar-right">
            <div className="legend">
              {["COACH", "WORKOUT_GENERATE", "WORKOUT_LOG", "CLARIFY"].map((r) => (
                <span className="legend-item" key={r}>
                  <span className="dot" style={{ background: ROUTE_META[r].color }} />
                  {ROUTE_META[r].label.replace("WORKOUT_", "")}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-inner">
            {messages.length === 0 && (
              <div className="empty-state">
                <div className="empty-icon">{Icons.dumbbell}</div>
                <div className="empty-title">Fresh thread · {thread}</div>
                <div className="empty-sub">Ask a coaching question, request a workout, or log a set. The hub router will pick an agent — expand “Show reasoning” on any reply to see the route, confidence, and tool calls.</div>
              </div>
            )}
            {messages.map((m, i) => (
              m.role === "user" ? (
                <div className="turn turn-user" key={m.id} data-screen-label={"turn-" + i}>
                  <div className="user-bubble">{m.text}</div>
                </div>
              ) : (
                <div className="turn turn-assistant" key={m.id} style={routeVars(m.turn.route)}>
                  <div className="assistant-head">
                    <span className="agent-avatar">{ROUTE_META[m.turn.route].icon}</span>
                    <span className="route-badge">{ROUTE_META[m.turn.route].agent}</span>
                    <span className="conf-chip">conf <b>{m.turn.confidence.toFixed(2)}</b></span>
                  </div>
                  <AssistantCard turn={m.turn} onPick={onPickClarify} />
                  <Trace turn={m.turn} defaultOpen={t.autoOpenTrace} />
                </div>
              )
            ))}
            {thinking && !messages.some((m) => m.turn && m.turn.streaming) && (
              <div className="turn turn-assistant">
                <div className="typing">
                  <span className="dots"><i /><i /><i /></span>
                  <span className="typing-label">routing…</span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="composer-wrap">
          <div className="composer">
            <textarea ref={taRef} rows="1" value={draft} placeholder="Ask, generate, or log a set…  (Enter to send)"
              onChange={onInput} onKeyDown={onKeyDown} />
            <button className="send-btn" disabled={!draft.trim() || thinking} onClick={() => send()}>{Icons.send}</button>
          </div>
          <div className="composer-hint">{model} · threshold {threshold.toFixed(2)}</div>
        </div>
      </main>

      <TweaksPanel>
        <TweakSection label="Appearance" />
        <TweakRadio label="Theme" value={t.theme} options={["light", "dark"]} onChange={(v) => setTweak("theme", v)} />
        <TweakColor label="Accent" value={t.accent} options={Object.keys(ACCENTS)} onChange={(v) => setTweak("accent", v)} />
        <TweakRadio label="Density" value={t.density} options={["compact", "comfortable"]} onChange={(v) => setTweak("density", v)} />
        <TweakSection label="Behavior" />
        <TweakToggle label="Color-code routes" value={t.routeColors} onChange={(v) => setTweak("routeColors", v)} />
        <TweakToggle label="Auto-open reasoning" value={t.autoOpenTrace} onChange={(v) => setTweak("autoOpenTrace", v)} />
      </TweaksPanel>
    </div>
  );
}

window.FitEngine.ready
  .catch((err) => console.error("dataset load failed:", err))
  .finally(() => ReactDOM.createRoot(document.getElementById("root")).render(<App />));
