import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import Hotspots from "./pages/Hotspots.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import LiveAirQuality from "./pages/LiveAirQuality.jsx";
import Forecast from "./pages/Forecast.jsx";
import "./index.css";
import "./oriva-light.css";

const API_URL = `${(import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "")}/api/chat`;
const newSession = () => globalThis.crypto?.randomUUID?.() || `oriva-${Date.now()}`;

function App() {
  const [view, setView] = useState("dashboard");
  const [sessionId, setSessionId] = useState(newSession);
  const [messages, setMessages] = useState([{
    role: "assistant",
    content: "Hello! I'm ORIVA, your air-pollution intelligence assistant. Ask me about air quality, weather, forecasts, historical hotspots, or CPCB policy."
  }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function sendMessage(event) {
    event.preventDefault();
    const message = input.trim();
    if (!message || busy) return;
    setMessages(old => [...old, { role: "user", content: message }]);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId })
      });
      if (!response.ok) throw new Error(`Chat API HTTP ${response.status}`);
      const data = await response.json();
      if (data.session_id) setSessionId(data.session_id);
      setMessages(old => [...old, {
        role: "assistant",
        content: data.answer || "No answer returned."
      }]);
    } catch (err) {
      setError(`${err.message}. Check the backend at http://127.0.0.1:8000.`);
    } finally {
      setBusy(false);
    }
  }

  const pageTitle = {
    chat: "ORIVA Assistant",
    dashboard: "Environmental overview",
    "live-aqi": "Live air quality & weather",
    map: "Historical hotspot intelligence",
    forecast: "Forecast & explainability"
  }[view] || "ORIVA";

  const pageSubtitle = {
    chat: "Multi-agent environmental intelligence",
    dashboard: "Current OpenAQ and OpenWeather conditions",
    "live-aqi": "OpenAQ measurements, timestamps, and freshness",
    map: "Historical DBSCAN clusters — not live readings",
    forecast: "PM2.5 forecast, station coverage, and SHAP transparency"
  }[view];

  function startNewChat() {
    setSessionId(newSession());
    setMessages([{ role: "assistant", content: "New chat started. What would you like to know about air quality or environmental policy?" }]);
    setInput("");
    setError("");
    setView("chat");
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <span className="brand-glyph" aria-hidden="true"><span /><span /><span /></span>
          <div><strong>ORIVA<span className="brand-period">.</span></strong><small>ENVIRONMENTAL INTELLIGENCE</small></div>
        </div>

        <button className="new-chat" onClick={startNewChat}>+ New conversation</button>
        <div className="side-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          <button type="button" className={`nav-item ${view === "chat" ? "active" : ""}`} onClick={() => setView("chat")}><span className="icon-mark">⌘</span><span>ORIVA Assistant</span></button>
          <button type="button" className={`nav-item ${view === "dashboard" ? "active" : ""}`} onClick={() => setView("dashboard")}><span className="icon-mark">▦</span><span>Overview</span></button>
          <button type="button" className={`nav-item ${view === "live-aqi" ? "active" : ""}`} onClick={() => setView("live-aqi")}><span className="icon-mark">◉</span><span>Live air quality</span><span className="nav-live">API</span></button>
          <button type="button" className={`nav-item ${view === "map" ? "active" : ""}`} onClick={() => setView("map")}><span className="icon-mark">⌖</span><span>Hotspot map</span></button>
          <button type="button" className={`nav-item ${view === "forecast" ? "active" : ""}`} onClick={() => setView("forecast")}><span className="icon-mark">↗</span><span>Forecast &amp; SHAP</span></button>
        </nav>

        <div className="side-label">ANALYTICS MODULES</div>
        <div className="capability">Forecasting &amp; XGBoost</div>
        <div className="capability">SHAP explainability</div>
        <div className="capability">CPCB policy &amp; RAG</div>
        <div className="sidebar-spacer" />
        <div className="sidebar-status">
          <span className="status-halo"><span /></span>
          <div><strong>Source-aware interface</strong><small>Freshness labels enabled</small></div>
        </div>
        <div className="sidebar-bottom"><span className="mini-brand-glyph">O</span><div><strong>ORIVA PLATFORM</strong><small>Research &amp; decision support</small></div><span>v1</span></div>
      </aside>

      <section className="main-shell">
        <header className="topbar">
          <div>
            <div className="breadcrumb"><span>ORIVA</span><i>/</i><strong>{pageTitle}</strong></div>
            <small>{pageSubtitle}</small>
          </div>
          <div className="topbar-right"><span className="topbar-env">PUNE / INDIA</span><span className="topbar-separator" /><span className="topbar-avatar">O</span></div>
        </header>

        {view === "dashboard" ? (
          <div className="page-scroll"><Dashboard /></div>
        ) : view === "live-aqi" ? (
          <div className="page-scroll"><LiveAirQuality /></div>
        ) : view === "map" ? (
          <div className="page-scroll"><Hotspots /></div>
        ) : view === "forecast" ? (
          <div className="page-scroll"><Forecast /></div>
        ) : (
          <>
            <div className="messages" aria-live="polite">
              {messages.map((m, i) => (
                <article className={`message ${m.role}`} key={i}>
                  <div className="avatar">{m.role === "assistant" ? "O" : "Y"}</div>
                  <div className="message-body">
                    <div className="message-name">{m.role === "assistant" ? "ORIVA" : "You"}</div>
                    <div className="message-content">{m.content}</div>
                  </div>
                </article>
              ))}
              {busy && <div className="typing">ORIVA is consulting specialist tools…</div>}
              {error && <div className="error-message" role="alert">{error}</div>}
            </div>
            <div className="composer-area">
              <form className="composer" onSubmit={sendMessage}>
                <textarea
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      e.currentTarget.form.requestSubmit();
                    }
                  }}
                  placeholder="Ask about station readings, forecasts, hotspots, or CPCB policy…"
                  rows={1}
                  aria-label="Message ORIVA"
                />
                <button className="send-button" type="submit" disabled={busy || !input.trim()} aria-label="Send message">↑</button>
              </form>
              <p className="disclaimer">Values depend on source availability. Check timestamps and official CPCB resources before operational decisions.</p>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
