import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import Hotspots from "./pages/Hotspots.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import "./index.css";

const API_URL = `${(import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "")}/api/chat`;
const newSession = () => globalThis.crypto?.randomUUID?.() || `oriva-${Date.now()}`;

function App() {
  const [view, setView] = useState("chat");
  const [sessionId, setSessionId] = useState(newSession);
  const [messages, setMessages] = useState([{
    role: "assistant",
    content: "Hello! I'm ORIVA, your air-pollution intelligence assistant. Ask me about AQI, weather, forecasts, hotspots, or CPCB policy."
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

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">O</span>
          <div><strong>ORIVA</strong><small>Pollution Intelligence</small></div>
        </div>

        <button className="new-chat" onClick={() => {
          setSessionId(newSession());
          setMessages([{ role: "assistant", content: "New chat started. What would you like to know?" }]);
          setInput("");
          setError("");
          setView("chat");
        }}>ï¼‹ New chat</button>

        <div className="side-label">WORKSPACE</div>
        <button type="button" className="capability" onClick={() => setView("chat")}>
          ðŸ’¬ <span>ORIVA Assistant</span>
        </button>
        <button type="button" className="capability" onClick={() => setView("map")}>
          ðŸ“ <span>Pollution Map</span>
        </button>

        <div className="side-label">SPECIALIST CAPABILITIES</div>
        <button type="button" className="capability" onClick={() => setView("dashboard")}>Environment &amp; live AQI</button>
        <div className="capability">ðŸ“ˆ <span>Forecasting & SHAP</span></div>
        <div className="capability">âš ï¸ <span>Hotspots & anomalies</span></div>
        <div className="capability">ðŸ“š <span>CPCB policy & RAG</span></div>
        <div className="capability">ðŸ’¡ <span>Recommendations</span></div>
        <div className="sidebar-note">One assistant. Multiple specialist agents.</div>
      </aside>

      <section className="chat-panel">
        <header className="topbar">
          <div>
            <strong>{view === "dashboard" ? "ORIVA Overview Dashboard" : view === "map" ? "ORIVA Pollution Map" : "ORIVA Assistant"}</strong>
            <span className="online-dot" />
            <small>{view === "dashboard" ? "Environmental metrics and station data" : view === "map" ? "Historical station analysis" : "Multi-agent environmental AI"}</small>
          </div>
          <span className="header-tag">AIR QUALITY â€¢ ENVIRONMENT â€¢ AI</span>
        </header>

        {view === "dashboard" ? (
          <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
            <Dashboard />
          </div>
        ) : view === "map" ? (
          <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
            <Hotspots />
          </div>
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
              {busy && <div className="typing">ORIVA is consulting specialist agentsâ€¦</div>}
              {error && <div className="error-message">{error}</div>}
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
                  placeholder="Ask about AQI, weather, forecasts, hotspots, or policyâ€¦"
                  rows={1}
                  aria-label="Message ORIVA"
                />
                <button className="send-button" type="submit" disabled={busy || !input.trim()}>â†‘</button>
              </form>
              <p className="disclaimer">Live results depend on data-source availability; verify important decisions against official sources.</p>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);