import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";

const API_URL = `${import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000"}/api/chat`;
const newSession = () => globalThis.crypto?.randomUUID?.() || `oriva-${Date.now()}`;

function App() {
  const [sessionId, setSessionId] = useState(newSession);
  const [messages, setMessages] = useState([{
    role: "assistant",
    content: "Hello! I'm ORIVA, your air-pollution intelligence assistant. Ask me about live AQI, weather, PM2.5 forecasts, pollution hotspots, SHAP explanations, or CPCB policy."
  }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function sendMessage(event) {
    event?.preventDefault();
    const message = input.trim();
    if (!message || busy) return;

    setMessages(current => [...current, { role: "user", content: message }]);
    setInput("");
    setBusy(true);
    setError("");

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, session_id: sessionId })
      });

      if (!response.ok) throw new Error(`Chat API returned HTTP ${response.status}`);
      const data = await response.json();
      if (data.session_id) setSessionId(data.session_id);

      setMessages(current => [...current, {
        role: "assistant",
        content: data.answer || "No answer was returned.",
        intent: data.intent,
        location: data.location,
        status: data.status
      }]);
    } catch {
      setError("Unable to reach ORIVA. Check that the backend is running at http://127.0.0.1:8000.");
    } finally {
      setBusy(false);
    }
  }

  function startNewChat() {
    setSessionId(newSession());
    setMessages([{
      role: "assistant",
      content: "New chat started. What would you like to know about air quality or the environment?"
    }]);
    setInput("");
    setError("");
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">O</span><div><strong>ORIVA</strong><small>Pollution Intelligence</small></div></div>
        <button className="new-chat" onClick={startNewChat}>＋ New chat</button>
        <div className="side-label">SPECIALIST CAPABILITIES</div>
        <div className="capability">☁️ <span>Environment & live AQI</span></div>
        <div className="capability">📈 <span>Forecasting & SHAP</span></div>
        <div className="capability">📍 <span>Hotspots & anomalies</span></div>
        <div className="capability">📚 <span>CPCB policy & RAG</span></div>
        <div className="capability">💡 <span>Recommendations</span></div>
        <div className="sidebar-note">One assistant. Multiple specialist agents.</div>
      </aside>

      <section className="chat-panel">
        <header className="topbar">
          <div><strong>ORIVA Assistant</strong><span className="online-dot" /> <small>Multi-agent environmental AI</small></div>
          <span className="header-tag">AIR QUALITY • WEATHER • AI</span>
        </header>

        <div className="messages" aria-live="polite">
          {messages.map((message, index) => (
            <article className={`message ${message.role}`} key={index}>
              <div className="avatar">{message.role === "assistant" ? "O" : "Y"}</div>
              <div className="message-body">
                <div className="message-name">{message.role === "assistant" ? "ORIVA" : "You"}</div>
                <div className="message-content">{message.content}</div>
                {message.role === "assistant" && (message.intent || message.location) && (
                  <div className="metadata">
                    {message.intent && <span>{message.intent.replaceAll("_", " ")}</span>}
                    {message.location && <span>{message.location}</span>}
                  </div>
                )}
              </div>
            </article>
          ))}
          {busy && <article className="message assistant"><div className="avatar">O</div><div className="message-body"><div className="message-name">ORIVA</div><div className="typing">Consulting specialist agents<span> ···</span></div></div></article>}
          {error && <div className="error-message">{error}</div>}
        </div>

        <div className="composer-area">
          <form className="composer" onSubmit={sendMessage}>
            <textarea
              value={input}
              onChange={event => setInput(event.target.value)}
              onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); } }}
              placeholder="Ask about AQI, weather, forecasts, hotspots, or policy…"
              rows={1}
              maxLength={4000}
              aria-label="Message ORIVA"
            />
            <button className="send-button" type="submit" disabled={busy || !input.trim()} aria-label="Send message">↑</button>
          </form>
          <p className="disclaimer">ORIVA uses specialist agents. Live results depend on data-source availability; verify important decisions against official sources.</p>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
