import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import Hotspots from "./pages/Hotspots.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import "./index.css";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const CHAT_URL = API_BASE + "/api/chat";
const newSession = () => globalThis.crypto?.randomUUID?.() || ("oriva-" + Date.now());
const sections = [
  { id: "overview", title: "Mission overview", icon: "◈" },
  { id: "dashboard", title: "Air quality dashboard", icon: "◉" },
  { id: "map", title: "Hotspot explorer", icon: "⌖" },
  { id: "chat", title: "ORIVA AI assistant", icon: "✳" }
];

function Brand() {
  return <div className="brand-lockup"><div className="brand-glyph"><span/><span/><span/></div><div><strong>ORIVA<span className="brand-period">.</span></strong><small>ATMOSPHERIC INTELLIGENCE</small></div></div>;
}

function Overview({ setView }) {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("Checking sources");
  const [checkedAt, setCheckedAt] = useState("");
  const [locationLabel, setLocationLabel] = useState("No station label returned");

  const refresh = async () => {
    setLoading(true);
    const endpoints = [
      ["pollution", "/api/pollution/current"],
      ["snapshot", "/api/current-snapshot/"],
      ["forecast", "/api/forecast/stations"]
    ];
    const results = await Promise.all(endpoints.map(async ([key, path]) => {
      try {
        const response = await fetch(API_BASE + path);
        if (!response.ok) throw new Error("HTTP " + response.status);
        return [key, await response.json(), true];
      } catch {
        return [key, null, false];
      }
    }));
    const next = {};
    results.forEach(([key, value, ok]) => { if (ok) next[key] = value; });
    setData(next);
    const successCount = results.filter(item => item[2]).length;
    setStatus(successCount === 3 ? "All sources responding" : successCount ? successCount + " of 3 sources responding" : "Backend not reachable");
    setCheckedAt(new Date().toLocaleTimeString());
    const source = [next.snapshot, next.pollution].filter(Boolean);
    const find = (value, keys, depth = 0) => {
      if (!value || typeof value !== "object" || depth > 4) return null;
      for (const key of keys) {
        if (value[key] !== undefined && value[key] !== null && typeof value[key] !== "object") return value[key];
      }
      for (const nested of Object.values(value)) {
        const result = find(nested, keys, depth + 1);
        if (result !== null) return result;
      }
      return null;
    };
    let station = null;
    source.some(item => {
      station = find(item, ["station_name", "station", "resolved_station", "location"]);
      return station !== null;
    });
    setLocationLabel(station || "No station label returned");
    setLoading(false);
  };

  useEffect(() => { refresh(); }, []);

  const findMetric = (keys) => {
    for (const item of [data.snapshot, data.pollution]) {
      if (!item) continue;
      const find = (value, depth = 0) => {
        if (!value || typeof value !== "object" || depth > 4) return null;
        for (const key of keys) {
          if (value[key] !== undefined && value[key] !== null && typeof value[key] !== "object") return value[key];
        }
        for (const nested of Object.values(value)) {
          const result = find(nested, depth + 1);
          if (result !== null) return result;
        }
        return null;
      };
      const result = find(item);
      if (result !== null) return result;
    }
    return null;
  };
  const aqi = findMetric(["aqi", "AQI", "air_quality_index", "overall_aqi"]);
  const pm25 = findMetric(["pm25", "PM2.5", "pm2_5", "pm25_mean"]);
  const pm10 = findMetric(["pm10", "PM10", "pm10_mean"]);
  const forecast = data.forecast;
  const forecastRows = Array.isArray(forecast) ? forecast : Object.values(forecast || {}).find(Array.isArray) || [];
  const metric = (label, value, unit, accent, index) => (
    <article className="metric-card" style={{ "--accent": accent }} key={label}>
      <div className="metric-top"><span>{label}</span><span className="metric-spark">{index}</span></div>
      <div className="metric-value">{value === null || value === undefined || value === "" ? "—" : value}<small>{value !== null && value !== undefined && value !== "" ? unit : ""}</small></div>
      <div className="metric-bottom"><span className="metric-dot"/>{value === null || value === undefined || value === "" ? "Data unavailable" : "Backend reported value"}</div>
    </article>
  );

  return <div className="overview-page page-enter">
    <div className="eyebrow"><span className="eyebrow-line"/> ENVIRONMENTAL COMMAND CENTER <span className="eyebrow-coordinate">PUNE REGION · STATION DATA</span></div>
    <section className="hero-panel">
      <div className="hero-grid"/>
      <div className="hero-copy">
        <div className="hero-kicker"><span className="pulse-dot"/> AIR QUALITY INTELLIGENCE PLATFORM</div>
        <h1>Understand the air.<br/><em>Change what comes next.</em></h1>
        <p>ORIVA combines monitoring data, predictive models and environmental knowledge to help turn pollution signals into informed action.</p>
        <div className="hero-actions"><button className="button-primary" onClick={() => setView("dashboard")}>Explore air quality <span>↗</span></button><button className="button-quiet" onClick={() => setView("chat")}>Ask ORIVA <span>→</span></button></div>
      </div>
      <div className="hero-orbit" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit orbit-three"/><div className="orbit-core"><div className="core-wave">≈</div><small>ATMOSPHERE<br/>IN MOTION</small></div><div className="orbit-label orbit-label-top"><span/> PARTICLE SIGNAL</div><div className="orbit-label orbit-label-bottom">PREDICT · EXPLAIN · ACT</div></div>
      <div className="hero-index"><span>01</span> / 04</div>
    </section>
    <div className="section-heading"><div><div className="section-overline">FIELD TELEMETRY</div><h2>Atmospheric snapshot</h2></div><div className="section-tools"><span className={"connection-pill " + (status === "All sources responding" ? "connected" : "")}><span/>{status}</span><button className="icon-button" onClick={refresh} disabled={loading} aria-label="Refresh data">{loading ? "…" : "↻"}</button></div></div>
    <section className="metric-grid">{metric("AIR QUALITY INDEX", aqi, "AQI", "#e5bb79", "01")}{metric("FINE PARTICLES", pm25, "µg/m³", "#66d5b4", "02")}{metric("COARSE PARTICLES", pm10, "µg/m³", "#91b5e9", "03")}{metric("FORECAST STATIONS", data.forecast ? forecastRows.length : null, "stations", "#c0a1ef", "04")}</section>
    <div className="data-footnote"><span className="tiny-pulse"/>{loading ? "Contacting backend endpoints…" : "Last checked at " + (checkedAt || "—")} <span className="footnote-separator">·</span> Only backend-returned values are displayed.</div>
    <div className="section-heading action-heading"><div><div className="section-overline">INTELLIGENCE WORKFLOWS</div><h2>From signal to response</h2></div><span className="section-aside">ONE WORKSPACE · MULTIPLE SPECIALISTS</span></div>
    <section className="workflow-grid">
      <button className="workflow-card" onClick={() => setView("dashboard")}><div className="workflow-icon mint">◉</div><div className="workflow-number">01 / MONITOR</div><h3>Air quality dashboard</h3><p>Inspect available AQI, particulate measurements and forecast station data from the connected backend.</p><span className="workflow-link">Open dashboard <b>↗</b></span><div className="workflow-glow"/></button>
      <button className="workflow-card" onClick={() => setView("map")}><div className="workflow-icon blue">⌖</div><div className="workflow-number">02 / LOCATE</div><h3>Hotspot explorer</h3><p>Explore station coordinates, historical PM2.5 summaries and DBSCAN cluster classifications.</p><span className="workflow-link">Explore map <b>↗</b></span><div className="workflow-glow"/></button>
      <button className="workflow-card" onClick={() => setView("chat")}><div className="workflow-icon violet">✳</div><div className="workflow-number">03 / INTERPRET</div><h3>Ask ORIVA</h3><p>Investigate pollution patterns, forecasting, SHAP explainability and CPCB guidance through the chat API.</p><span className="workflow-link">Open assistant <b>↗</b></span><div className="workflow-glow"/></button>
    </section>
    <section className="operating-note"><div className="note-icon">i</div><div><strong>Evidence before inference</strong><p>Historical hotspot analysis is not presented as live pollution. Missing values remain unavailable rather than being guessed.</p></div><span className="note-tag">DATA-INFORMED</span></section>
    <footer className="page-footer"><span>ORIVA <b>●</b> ENVIRONMENTAL INTELLIGENCE</span><span>Location label: {String(locationLabel)} <i>·</i> {checkedAt || "Awaiting first refresh"}</span></footer>
  </div>;
}

function ChatView() {
  const [sessionId, setSessionId] = useState(newSession);
  const [messages, setMessages] = useState([{ role: "assistant", content: "I’m ORIVA, your air-pollution intelligence assistant. I can help interpret AQI data, PM2.5 forecasts, hotspot analysis, SHAP explanations and CPCB policy documents. What would you like to explore?" }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function sendMessage(event) {
    event.preventDefault();
    const message = input.trim();
    if (!message || busy) return;
    setMessages(current => [...current, { role: "user", content: message }]);
    setInput(""); setBusy(true); setError("");
    try {
      const response = await fetch(CHAT_URL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, session_id: sessionId }) });
      if (!response.ok) throw new Error("Chat API returned HTTP " + response.status);
      const data = await response.json();
      if (data.session_id) setSessionId(data.session_id);
      setMessages(current => [...current, { role: "assistant", content: data.answer || "No answer was returned.", intent: data.intent, location: data.location }]);
    } catch (err) {
      setError((err.message || "Request failed") + ". Check the backend at " + API_BASE + ".");
    } finally { setBusy(false); }
  }
  return <div className="chat-page page-enter"><div className="eyebrow"><span className="eyebrow-line"/> CONVERSATIONAL INTELLIGENCE <span className="eyebrow-coordinate">SESSION-BASED · API CONNECTED</span></div><div className="chat-intro"><div className="assistant-orb">✳</div><div><div className="section-overline">ORIVA / AI ASSISTANT</div><h1>Make sense of the signal.</h1><p>Ask targeted questions about air quality, forecasts, hotspots or environmental policy.</p></div></div>
    <div className="prompt-chips">{["Explain PM2.5 vs PM10", "How do DBSCAN hotspots work?", "Explain SHAP for an air-quality forecast", "Summarize CPCB policy guidance"].map(prompt => <button key={prompt} onClick={() => setInput(prompt)}>{prompt}<span>↗</span></button>)}</div>
    <section className="chat-console"><div className="console-head"><div><span className="pulse-dot"/><strong>ORIVA CONVERSATION</strong><small>Specialist orchestration</small></div><button className="text-action" onClick={() => { setSessionId(newSession()); setMessages([{ role: "assistant", content: "Fresh session started. What would you like to investigate?" }]); setError(""); }}>＋ New session</button></div>
      <div className="console-messages" aria-live="polite">{messages.map((message, index) => <article className={"chat-message " + message.role} key={index}><div className={"chat-avatar " + message.role}>{message.role === "assistant" ? "O" : "YOU"}</div><div className="chat-message-body"><div className="chat-message-name">{message.role === "assistant" ? "ORIVA" : "YOU"}<span>{message.role === "assistant" ? " · ENVIRONMENTAL AI" : ""}</span></div><div className="chat-message-content">{message.content}</div>{(message.intent || message.location) && <div className="chat-metadata">{message.intent && <span>{String(message.intent).replaceAll("_", " ")}</span>}{message.location && <span>{message.location}</span>}</div>}</div></article>)}{busy && <article className="chat-message assistant"><div className="chat-avatar assistant">O</div><div className="chat-message-body"><div className="chat-message-name">ORIVA<span> · WORKING</span></div><div className="typing-indicator"><i/><i/><i/><span>Consulting connected services</span></div></div></article>}{error && <div className="chat-error" role="alert">{error}</div>}</div>
      <form className="chat-composer" onSubmit={sendMessage}><textarea value={input} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form.requestSubmit(); } }} placeholder="Ask ORIVA about an observation, forecast or policy…" rows={2} maxLength={4000} aria-label="Message ORIVA"/><button disabled={busy || !input.trim()} type="submit" aria-label="Send message">↑</button><small>Enter to send · Shift + Enter for a new line</small></form>
    </section><p className="chat-disclaimer">Responses depend on backend availability, connected data sources and retrieved context. Verify consequential decisions with official sources.</p></div>;
}

function App() {
  const [view, setView] = useState("overview");
  const titles = { overview: "Mission overview", dashboard: "Air quality dashboard", map: "Hotspot explorer", chat: "ORIVA AI assistant" };
  return <main className="app-shell"><aside className="sidebar"><Brand/><div className="workspace-chip"><span className="workspace-chip-icon">⌘</span><div><small>WORKSPACE</small><strong>Pollution intelligence</strong></div><span className="chevron">⌄</span></div>
    <div className="side-label">NAVIGATION</div><nav className="primary-nav" aria-label="Main navigation"><button className={"nav-item " + (view === "overview" ? "active" : "")} onClick={() => setView("overview")}><span className="icon-mark">◈</span><span>Mission overview</span><b>↗</b></button></nav>
    <div className="side-label">INTELLIGENCE TOOLS</div><nav className="primary-nav" aria-label="Intelligence tools">{sections.slice(1).map(item => <button key={item.id} className={"nav-item " + (view === item.id ? "active" : "")} onClick={() => setView(item.id)}><span className="icon-mark">{item.icon}</span><span>{item.title}</span>{item.id === "chat" && <b className="nav-live">AI</b>}</button>)}</nav>
    <div className="sidebar-spacer"/><div className="sidebar-status"><div className="status-halo"><span/></div><div><strong>ORIVA core</strong><small>Environment intelligence</small></div><span className="status-led"/></div><div className="sidebar-bottom"><div className="mini-brand-glyph">O</div><div><strong>ORIVA PLATFORM</strong><small>Field operations interface</small></div><span>v1.0</span></div>
  </aside><section className="main-shell"><header className="topbar"><div className="breadcrumb"><span>ORIVA</span><i>/</i><strong>{titles[view]}</strong></div><div className="topbar-right"><span className="topbar-env"><span className="tiny-pulse"/> ENVIRONMENT SYSTEMS</span><span className="topbar-separator"/><div className="topbar-avatar">O</div></div></header>
    <div className="page-scroll">{view === "overview" && <Overview setView={setView}/>}{view === "dashboard" && <div className="legacy-page page-enter"><div className="eyebrow"><span className="eyebrow-line"/> LIVE API EXPLORER <span className="eyebrow-coordinate">ENVIRONMENTAL METRICS / FORECAST STATIONS</span></div><Dashboard/></div>}{view === "map" && <div className="legacy-page page-enter"><div className="eyebrow"><span className="eyebrow-line"/> SPATIAL ANALYSIS <span className="eyebrow-coordinate">HISTORICAL STATION CLUSTERS</span></div><Hotspots/></div>}{view === "chat" && <ChatView/>}</div>
    <nav className="mobile-nav" aria-label="Mobile navigation">{sections.map(item => <button key={item.id} className={"mobile-nav-item " + (view === item.id ? "active" : "")} onClick={() => setView(item.id)}><span>{item.icon}</span><small>{item.id === "overview" ? "Home" : item.id === "dashboard" ? "AQI" : item.id === "map" ? "Map" : "AI"}</small></button>)}</nav>
  </section></main>;
}
createRoot(document.getElementById("root")).render(<App/>);
