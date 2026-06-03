/* components.jsx — presentational pieces for the multi-agent console.
   Exports to window so app.jsx can use them. */
const { useState } = React;
const EX = window.FitEngine.byId;

/* ----------------------------------------------------------- icons */
function Icon({ d, size = 16, stroke = 2, fill, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill || "none"}
      stroke={fill ? "none" : "currentColor"} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" {...rest}>
      {d}
    </svg>
  );
}
const Icons = {
  dumbbell: <Icon d={<><path d="M6.5 6.5l11 11"/><path d="M21 21l-1-1"/><path d="M3 3l1 1"/><path d="M18 22l4-4"/><path d="M2 6l4-4"/><path d="M3 10l7-7"/><path d="M14 21l7-7"/></>} />,
  send: <Icon d={<><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></>} size={17} />,
  reset: <Icon d={<><path d="M3 12a9 9 0 109-9 9 9 0 00-6.4 2.6L3 8"/><path d="M3 3v5h5"/></>} size={14} />,
  brain: <Icon d={<><path d="M12 5a3 3 0 00-3 3v0a3 3 0 00-2 5 3 3 0 002 5 3 3 0 005 0 3 3 0 002-5 3 3 0 00-2-5 3 3 0 00-3-3z"/><path d="M12 5v14"/></>} size={15} />,
  chevron: <Icon d={<path d="M9 6l6 6-6 6"/>} size={12} stroke={2.4} />,
  clock: <Icon d={<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>} size={13} />,
  target: <Icon d={<><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1" fill="currentColor"/></>} size={13} />,
  gear: <Icon d={<><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-1.8-.3 1.6 1.6 0 00-1 1.5V21a2 2 0 01-4 0v-.1a1.6 1.6 0 00-1-1.5 1.6 1.6 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.6 1.6 0 00.3-1.8 1.6 1.6 0 00-1.5-1H3a2 2 0 010-4h.1a1.6 1.6 0 001.5-1 1.6 1.6 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.6 1.6 0 001.8.3H9a1.6 1.6 0 001-1.5V3a2 2 0 014 0v.1a1.6 1.6 0 001 1.5 1.6 1.6 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00-.3 1.8V9a1.6 1.6 0 001.5 1H21a2 2 0 010 4h-.1a1.6 1.6 0 00-1.5 1z"/></>} size={13} />,
  check: <Icon d={<path d="M20 6L9 17l-5-5"/>} size={14} stroke={2.6} />,
  alert: <Icon d={<><path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L14.4 3.9a2 2 0 00-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></>} size={15} />,
  spark: <Icon d={<path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17l-1.9-5.1L4.5 10l5.6-1.4L12 3z"/>} size={13} />,
  route: <Icon d={<><circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 000-7h-11a3.5 3.5 0 010-7H15"/><circle cx="18" cy="5" r="3"/></>} size={14} />,
  book: <Icon d={<><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></>} size={13} />,
  layers: <Icon d={<><path d="M12 2l9 5-9 5-9-5 9-5z"/><path d="M3 12l9 5 9-5"/><path d="M3 17l9 5 9-5"/></>} size={13} />,
};

/* ----------------------------------------------------------- route theming */
const ROUTE_META = {
  COACH:            { label: "COACH",            color: "var(--r-coach)",    bg: "var(--r-coach-bg)",    ring: "var(--r-coach-ring)",    icon: Icons.book,    agent: "Coach Agent" },
  WORKOUT_GENERATE: { label: "WORKOUT_GENERATE", color: "var(--r-generate)", bg: "var(--r-generate-bg)", ring: "var(--r-generate-ring)", icon: Icons.dumbbell,agent: "Generator Agent" },
  WORKOUT_LOG:      { label: "WORKOUT_LOG",      color: "var(--r-log)",      bg: "var(--r-log-bg)",      ring: "var(--r-log-ring)",      icon: Icons.check,   agent: "Logger Agent" },
  CLARIFY:          { label: "CLARIFY",          color: "var(--r-clarify)",  bg: "var(--r-clarify-bg)",  ring: "var(--r-clarify-ring)",  icon: Icons.route,   agent: "Hub Router" },
};
function routeVars(route) {
  const m = ROUTE_META[route] || ROUTE_META.CLARIFY;
  return { "--route-color": m.color, "--route-bg": m.bg, "--route-ring": m.ring };
}

/* ----------------------------------------------------------- JSON snippet */
function JsonInline({ obj }) {
  if (!obj) return null;
  const parts = Object.entries(obj).map(([k, v], i) => (
    <span key={k}>
      {i > 0 ? ", " : ""}
      <span className="json-key">{k}</span>: {Array.isArray(v) ? "[" + v.join(", ") + "]" : JSON.stringify(v)}
    </span>
  ));
  return <span className="json-pre">{"{ "}{parts}{" }"}</span>;
}

/* ----------------------------------------------------------- TRACE expander */
function safeTraceText(val) {
  if (val == null) return null;
  if (typeof val === "string" || typeof val === "number" || typeof val === "boolean") return String(val);
  return JSON.stringify(val);
}

function normalizeTraceStep(ev) {
  if (!ev) return { kind: "note", label: "" };
  if (ev.kind === "router" || ev.kind === "tool" || ev.kind === "recover" || ev.kind === "agent" || ev.kind === "note") {
    return ev;
  }
  const kind = ev.kind;
  const detail = ev.detail || {};
  if (kind === "route") {
    return {
      kind: "router",
      label: "route_query",
      out: `${detail.route || "?"} · ${Number(detail.confidence || 0).toFixed(2)}`,
    };
  }
  if (kind === "tool_call") {
    if (detail.args != null) {
      return {
        kind: "tool",
        label: "search_exercises",
        input: detail.args,
        out: detail.count != null ? `${detail.count} results` : undefined,
        count: detail.count,
      };
    }
    if (detail.score != null) {
      return { kind: "tool", label: "fuzzy_match", out: `score ${Number(detail.score).toFixed(0)}` };
    }
    if (detail.title != null) {
      return { kind: "tool", label: "build_workout", out: `ok · ${detail.title}` };
    }
    return { kind: "tool", label: ev.label || "tool", out: ev.label };
  }
  if (kind === "recovery") {
    if (detail.args != null) {
      return { kind: "recover", label: "fallback", out: "0 results → relaxing filters and re-searching", count: 0 };
    }
    if (detail.message != null) {
      return { kind: "recover", label: "rejected", out: String(detail.message) };
    }
    return { kind: "recover", label: "fallback", out: ev.label || "recovered" };
  }
  if (kind === "agent") return { kind: "agent", label: ev.label || "agent" };
  if (kind === "clarify") {
    const conf = detail.confidence;
    return {
      kind: "note",
      label: "gate",
      out: conf != null ? `${Number(conf).toFixed(2)} below threshold → CLARIFY` : (ev.label || "CLARIFY"),
    };
  }
  return { kind: "note", label: ev.label || "" };
}

function normalizeTrace(trace) {
  return (trace || []).map(normalizeTraceStep);
}

function Trace({ turn, defaultOpen }) {
  const [open, setOpen] = useState(!!defaultOpen);
  const steps = normalizeTrace(turn.trace);
  const hasRecover = steps.some((s) => s.kind === "recover" || s.count === 0);
  const m = ROUTE_META[turn.route] || ROUTE_META.CLARIFY;
  const conf = Number(turn.confidence ?? 0);

  return (
    <div className="trace" style={routeVars(turn.route || "CLARIFY")}>
      <button type="button" className="trace-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="chev">{Icons.chevron}</span>
        {Icons.brain}
        <span>Show reasoning</span>
        <span style={{ color: "var(--text-3)" }}>· {m.label.toLowerCase()} · {conf.toFixed(2)}</span>
        {hasRecover && <span className="recover-flag">{Icons.alert}recovered</span>}
      </button>
      {open && (
        <div className="trace-panel">
          <div className="trace-meta">
            <div className="trace-meta-row">
              <span className="k">route</span>
              <span className="route-badge" style={{ fontSize: 10 }}>{m.icon}{m.label}</span>
              {turn.downgradedFrom && <span className="conf-chip">downgraded from <b>{turn.downgradedFrom}</b></span>}
            </div>
            <div className="trace-meta-row">
              <span className="k">confidence</span>
              <div className="confbar"><i style={{ width: (conf * 100) + "%" }} /></div>
              <span className="conf-chip"><b>{conf.toFixed(2)}</b>{turn.threshold != null ? " / thr " + Number(turn.threshold).toFixed(2) : ""}</span>
            </div>
            {turn.candidates && (
              <div className="trace-meta-row">
                <span className="k">candidates</span>
                <span className="v" style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
                  {turn.candidates.map((c) => c.route.replace("WORKOUT_", "") + " " + c.p.toFixed(2)).join("  ·  ")}
                </span>
              </div>
            )}
            <div className="trace-meta-row">
              <span className="k">rationale</span>
              <span className="v rationale">{turn.rationale || (turn.streaming ? "Routing in progress…" : "—")}</span>
            </div>
          </div>
          {turn.streaming && (
            <div className="trace-streaming-note">Agents still running — trace updates live.</div>
          )}
          <div className="trace-steps">
            {steps.length === 0 && turn.streaming ? (
              <div className="trace-empty">Waiting for router…</div>
            ) : (
              steps.map((s, i) => <TraceStep key={i} step={s} />)
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TraceStep({ step }) {
  const kindLabel = { router: "route", tool: "tool", recover: "recover", agent: "agent", note: "note" }[step.kind] || step.kind;
  const detailText = safeTraceText(step.detail);
  return (
    <div className="tstep" data-kind={step.kind}>
      <div className="tstep-rail"><span className="tstep-dot" /></div>
      <div className="tstep-body">
        <div className="tstep-label">
          <span className="kind-tag">{kindLabel}</span>
          {step.label}
        </div>
        <div className="tstep-io">
          {detailText && <span>{detailText} </span>}
          {step.input && (<><JsonInline obj={step.input} /> <span className="arrow">→</span> </>)}
          {step.out && (
            <span className={"out" + (step.count === 0 ? " count0" : "")}>{step.out}</span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- assistant CARDS */
const JOINTS_GROUP_HINT =
  "Joints under load across this workout, based on joints_loaded in the exercise library.";

function JointsLoaded({ joints, style }) {
  if (!joints || !joints.length) return null;
  return (
    <div className="joints-loaded" style={style} title={JOINTS_GROUP_HINT}>
      <div className="refs-label joints-loaded-label" title={JOINTS_GROUP_HINT}>
        Joints loaded
      </div>
      <div className="coach-tags joints-loaded-tags">
        {joints.map((j) => (
          <span
            key={j}
            className="tag tag-joint"
            title={`${j} — under load from at least one exercise in this session`}
          >
            {j}
          </span>
        ))}
      </div>
    </div>
  );
}

function CoachCard({ content }) {
  const html = window.renderMarkdown ? window.renderMarkdown(content.prose) : content.prose;
  return (
    <div className="card card-accent" style={routeVars("COACH")}>
      <div className="coach-body">
        <div className="coach-prose" dangerouslySetInnerHTML={{ __html: html }} />
        <JointsLoaded joints={content.joints} />
        {content.refs && content.refs.length > 0 && (
          <>
            <div className="refs-label">Exercises referenced</div>
            <div className="coach-tags">
              {content.refs.map((id) => (
                <span key={id} className="ref-chip">{Icons.dumbbell}{EX[id] ? EX[id].name : id}</span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ExRow({ item }) {
  const ex = EX[item.id] || { name: item.id, equipment_required: [] };
  return (
    <div className="ex-row">
      <div className="ex-main">
        <div className="ex-name">{ex.name}</div>
        <div className="ex-sub">
          <span className="mono">{(ex.equipment_required || []).join(" · ")}</span>
          {ex.priority_tier && <span>tier {ex.priority_tier}</span>}
        </div>
      </div>
      <div className="ex-prescribe">
        <span className="sr">{item.sets}×{item.reps}</span>
        {item.rest !== "—" && <span className="rest">{item.rest} rest</span>}
      </div>
    </div>
  );
}

function WorkoutCard({ content }) {
  return (
    <div className="card card-accent" style={routeVars("WORKOUT_GENERATE")}>
      <div className="wk-head">
        <div className="wk-title">{content.title}</div>
        <div className="wk-meta">
          <span>{Icons.clock}<span className="mono">{content.meta.duration}</span></span>
          <span>{Icons.target}{content.meta.focus}</span>
          <span>{Icons.dumbbell}<span className="mono">{content.meta.equipment.join(" + ")}</span></span>
        </div>
      </div>
      {content.recovered && (
        <p className="wk-recover">{Icons.alert}<span>{content.recovered}</span></p>
      )}
      <JointsLoaded joints={content.joints} style={{ padding: "0 14px 8px" }} />
      {content.sections.map((sec) => (
        <div className="wk-section" key={sec.name}>
          <div className="wk-section-name">{sec.name}</div>
          {sec.items.map((it, i) => <ExRow key={i} item={it} />)}
        </div>
      ))}
    </div>
  );
}

function LogCard({ content }) {
  return (
    <div className="card card-accent" style={routeVars("WORKOUT_LOG")}>
      <div className="log-card-body">
        <div className="log-card-head">{Icons.check}<span>Parsed and logged to this thread</span></div>
        {content.entries.map((e, i) => {
          const ex = EX[e.matched_id];
          return (
            <div className="log-entry" key={i}>
              <div>
                <div className="le-matched">{ex ? ex.name : e.matched_id}</div>
                <div className="le-fuzzy">
                  “{e.raw}” <span className="le-arrow">→</span> matched <span className="le-score">{e.score.toFixed(2)}</span>
                </div>
              </div>
              <div className="le-prescribe">
                {e.sets}×{e.reps}
                <small>{e.weight} {e.unit}</small>
              </div>
            </div>
          );
        })}
        <div className="log-confirm">{Icons.spark}Saved · visible in the Session Log →</div>
      </div>
    </div>
  );
}

function ClarifyCard({ content, onPick }) {
  return (
    <div className="card card-accent" style={routeVars("CLARIFY")}>
      <div className="clarify-body">
        <p className="clarify-q">{content.question}</p>
        <div className="clarify-opts">
          {content.options.map((o) => (
            <button key={o} className="clarify-opt" onClick={() => onPick && onPick(o)}>{o}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

function AssistantCard({ turn, onPick }) {
  const t = turn.content.type;
  if (t === "coach") return <CoachCard content={turn.content} />;
  if (t === "workout") return <WorkoutCard content={turn.content} />;
  if (t === "log") return <LogCard content={turn.content} />;
  if (t === "clarify") return <ClarifyCard content={turn.content} onPick={onPick} />;
  return null;
}

Object.assign(window, {
  Icons, ROUTE_META, routeVars, Trace, AssistantCard,
  CoachCard, WorkoutCard, LogCard, ClarifyCard, ExRow,
  normalizeTrace,
});
