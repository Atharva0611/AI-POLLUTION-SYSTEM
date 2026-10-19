import { useCallback, useEffect, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const LOCATIONS = ["Pune", "Pimpri-Chinchwad", "Kharadi", "Wagholi", "Hinjawadi", "Shivajinagar", "Hadapsar", "Baner", "Kothrud", "Pimpri", "Chinchwad", "Bhosari", "Akurdi", "Nigdi"];

const TASKS = [
  { id: "aqi", label: "Live AQI", prompt: location => `AQI of ${location}`, icon: "◉", description: "Current available air-quality data" },
  { id: "weather", label: "Weather", prompt: location => `Current weather and its possible impact on air pollution in ${location}`, icon: "☼", description: "Weather context and dispersion conditions" },
  { id: "sources", label: "Source analysis", prompt: location => `Analyze possible pollution sources in ${location} using available observations, weather context, and RAG evidence. Clearly distinguish suspected sources from verified causes.`, icon: "⌁", description: "Evidence-based potential contributors" },
  { id: "forecast", label: "Forecast", prompt: location => `Give the available PM2.5 forecast for ${location}. Clearly label predictions, model limitations, and forecast horizon.`, icon: "↗", description: "Model output when available" },
  { id: "rag", label: "CPCB guidance", prompt: location => `Explain the relevant CPCB air-quality health guidance for ${location} using retrieved documents and cite the available sources.`, icon: "▤", description: "Retrieved policy and health guidance" },
];

function getAnswerText(data) {
  return data?.answer || data?.response || data?.message || "The assistant returned no answer.";
}

export default function Intelligence() {
  const [location, setLocation] = useState("Pune");
  const [customLocation, setCustomLocation] = useState("");
  const [activeTask, setActiveTask] = useState("aqi");
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [checkedAt, setCheckedAt] = useState("");
  const [sessionId, setSessionId] = useState(() => globalThis.crypto?.randomUUID?.() || `oriva-${Date.now()}`);
  const [hotspots, setHotspots] = useState({ status: "loading", count: null, message: "" });
  const [geoStatus, setGeoStatus] = useState("");

  const loadHotspots = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/hotspots/`, { signal: AbortSignal.timeout(15000) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
      setHotspots({ status: "ok", count: Number(data.count ?? data.hotspots?.length ?? 0), message: data.message || "Historical hotspot dataset returned by backend.", source: data.source });
    } catch (err) {
      setHotspots({ status: "unavailable", count: null, message: err.message || "Hotspot service unavailable." });
    }
  }, []);

  useEffect(() => { loadHotspots(); }, [loadHotspots]);

  const runQuery = async (prompt, taskId = activeTask) => {
    const clean = String(prompt || "").trim();
    if (!clean || busy) return;
    setBusy(true);
    setError("");
    setActiveTask(taskId);
    setQuestion(clean);
    setResult(null);
    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: clean, session_id: sessionId }),
        signal: AbortSignal.timeout(45000),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Chat API returned HTTP ${response.status}`);
      if (data.session_id) setSessionId(data.session_id);
      setResult({ answer: getAnswerText(data), intent: data.intent || null, location: data.location || null, status: data.status || "returned", raw: data });
      setCheckedAt(new Date().toLocaleString());
    } catch (err) {
      setError(err.name === "TimeoutError" ? "The request timed out. The provider or agent may be slow; retry in a moment." : `${err.message || "Request failed"}. Confirm that FastAPI is running at ${API_BASE}.`);
    } finally {
      setBusy(false);
    }
  };

  const selectedTask = TASKS.find(task => task.id === activeTask) || TASKS[0];
  const chooseLocation = value => {
    setLocation(value);
    setCustomLocation("");
  };
  const searchLocation = customLocation.trim() || location;

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setGeoStatus("This browser does not support geolocation. Search for a locality instead.");
      return;
    }
    setGeoStatus("Requesting browser location permission…");
    navigator.geolocation.getCurrentPosition(
      position => {
        const { latitude, longitude } = position.coords;
        setCustomLocation(`${latitude.toFixed(5)}, ${longitude.toFixed(5)}`);
        setGeoStatus("Coordinates received. The assistant may need a named locality for accurate resolution.");
      },
      err => setGeoStatus(err.code === 1 ? "Location permission was denied. Manual search still works." : "Could not read your location. Try searching for a locality."),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
    );
  };

  return (
    <main className="oriva-intel page-enter">
      <style>{`
        .oriva-intel{--intel-line:rgba(177,215,198,.13);padding:clamp(18px,3vw,34px);display:grid;gap:22px;color:#e9f1ed;align-content:start}
        .intel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}
        .intel-eyebrow{font:10px 'DM Mono',monospace;letter-spacing:.16em;color:#7de0b7;text-transform:uppercase}
        .intel-head h1{font-size:clamp(27px,3.2vw,42px);letter-spacing:-.04em;margin:9px 0}
        .intel-muted{color:#8da29a;font-size:13px;line-height:1.65;max-width:720px}
        .intel-live{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--intel-line);border-radius:99px;padding:8px 11px;font:10px 'DM Mono',monospace;color:#b9d8ca}
        .intel-live i{width:7px;height:7px;border-radius:50%;background:#7de0b7;box-shadow:0 0 0 4px #7de0b71b}
        .intel-search-panel{border:1px solid var(--intel-line);border-radius:19px;padding:clamp(16px,2.5vw,25px);background:linear-gradient(125deg,rgba(26,65,52,.48),rgba(13,24,21,.94) 62%);box-shadow:0 18px 55px #00000018}
        .intel-search-grid{display:grid;grid-template-columns:minmax(180px,1fr) minmax(220px,1.2fr) auto;gap:10px}
        .intel-control{min-width:0;background:#0a1210;border:1px solid var(--intel-line);border-radius:10px;color:#e9f1ed;padding:12px 13px;width:100%;font:12px inherit}
        .intel-control:focus{outline:2px solid #7de0b7;outline-offset:2px}
        .intel-button{border:1px solid #7de0b7;background:#7de0b7;color:#071711;border-radius:10px;padding:12px 16px;font-weight:800;font-size:12px;white-space:nowrap;cursor:pointer;transition:transform .18s,filter .18s}
        .intel-button:hover{transform:translateY(-1px);filter:brightness(1.06)}.intel-button:disabled{opacity:.55;cursor:wait;transform:none}
        .intel-button-quiet{background:transparent;color:#c6ddd2;border:1px solid var(--intel-line)}
        .intel-quick{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
        .intel-chip{border:1px solid var(--intel-line);background:#ffffff06;color:#b9cfc4;border-radius:99px;padding:7px 10px;font-size:11px;cursor:pointer}
        .intel-chip:hover{border-color:#7de0b780;color:#e9f1ed}
        .intel-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:11px}
        .intel-task{min-width:0;text-align:left;border:1px solid var(--intel-line);background:#0d1714;border-radius:14px;padding:15px;display:grid;gap:10px;color:#e9f1ed;cursor:pointer;transition:border-color .2s,transform .2s,background .2s}
        .intel-task:hover{transform:translateY(-2px);border-color:#7de0b76b}.intel-task.selected{border-color:#7de0b7;background:linear-gradient(145deg,#16382c,#0e1915)}
        .intel-task-icon{font-size:21px;color:#7de0b7}.intel-task strong{font-size:12px}.intel-task small{font-size:10px;line-height:1.5;color:#8da29a}
        .intel-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px}
        .intel-stat{border:1px solid var(--intel-line);border-radius:14px;padding:16px;background:#0d1714;min-width:0}
        .intel-stat span{display:block;font:9px 'DM Mono',monospace;letter-spacing:.12em;color:#82978d;text-transform:uppercase}.intel-stat strong{display:block;font-size:23px;margin-top:11px;overflow-wrap:anywhere}.intel-stat small{display:block;font-size:10px;color:#82978d;margin-top:7px;line-height:1.5}
        .intel-result{border:1px solid var(--intel-line);border-radius:17px;background:#0d1714;overflow:hidden;min-width:0}
        .intel-result-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:16px 18px;border-bottom:1px solid var(--intel-line)}
        .intel-result-title{display:flex;align-items:center;gap:9px;font-size:12px;font-weight:800}.intel-result-title i{width:7px;height:7px;border-radius:50%;background:${busy ? "#e5bb79" : "#7de0b7"};animation:intel-pulse 1.6s infinite}
        .intel-result-body{padding:20px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.8;color:#c9d9d0;max-height:600px;overflow:auto}
        .intel-result-meta{display:flex;gap:7px;flex-wrap:wrap}.intel-tag{font:9px 'DM Mono',monospace;padding:5px 7px;border:1px solid var(--intel-line);border-radius:6px;color:#a7c4b6;text-transform:uppercase}
        .intel-empty{padding:30px 20px;text-align:center;color:#8da29a;font-size:12px;line-height:1.8}
        .intel-error{border:1px solid #b65b5b77;background:#61272726;color:#ffc6c6;border-radius:12px;padding:13px;font-size:12px;line-height:1.6}
        .intel-note{border-left:2px solid #d9b575;padding:9px 12px;color:#a7b8ae;font-size:11px;line-height:1.6;background:#d9b57508}
        @keyframes intel-pulse{50%{opacity:.35;box-shadow:0 0 0 5px #7de0b715}}
        @media(max-width:1000px){.intel-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.intel-search-grid{grid-template-columns:1fr 1fr}.intel-search-grid .intel-button{grid-column:1/-1}}
        @media(max-width:650px){.intel-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.intel-stats{grid-template-columns:1fr}.intel-search-grid{grid-template-columns:1fr}.intel-search-grid .intel-button{grid-column:auto}.intel-head h1{font-size:29px}}
        @media(prefers-reduced-motion:reduce){.intel-task,.intel-button{transition:none}.intel-result-title i{animation:none}}
      `}</style>

      <header className="intel-head">
        <div><div className="intel-eyebrow">ORIVA / Location intelligence</div><h1>Explore the air around you.</h1><p className="intel-muted">Ask the existing LangGraph assistant for location-specific air quality, weather context, forecasts, potential pollution contributors, or retrieved CPCB guidance. Results below come from the backend response.</p></div>
        <span className="intel-live"><i/> API-DRIVEN WORKSPACE</span>
      </header>

      <section className="intel-search-panel">
        <div className="intel-eyebrow" style={{ marginBottom: 13 }}>SELECT AREA · RUN AN ANALYSIS</div>
        <div className="intel-search-grid">
          <select className="intel-control" aria-label="Select locality" value={location} onChange={event => { chooseLocation(event.target.value); }}><optgroup label="Pune region">{LOCATIONS.map(item => <option key={item}>{item}</option>)}</optgroup></select>
          <input className="intel-control" aria-label="Custom location or coordinates" placeholder="Or enter a locality / coordinates" value={customLocation} onChange={event => setCustomLocation(event.target.value)} onKeyDown={event => { if (event.key === "Enter") runQuery(TASKS.find(t => t.id === activeTask).prompt(searchLocation)); }} />
          <button className="intel-button" disabled={busy} onClick={() => runQuery(TASKS.find(t => t.id === activeTask).prompt(searchLocation))}>{busy ? "Analyzing…" : "Run analysis ↗"}</button>
        </div>
        <div className="intel-quick">{LOCATIONS.slice(2, 8).map(item => <button className="intel-chip" key={item} onClick={() => { chooseLocation(item); }}>{item}</button>)}<button className="intel-chip" onClick={useMyLocation}>⌖ Use my location</button></div>
        {geoStatus && <p className="intel-muted" role="status" style={{ marginBottom: 0 }}>{geoStatus}</p>}
      </section>

      <section className="intel-grid" aria-label="Analysis types">{TASKS.map(task => <button key={task.id} className={`intel-task ${activeTask === task.id ? "selected" : ""}`} onClick={() => { setActiveTask(task.id); setError(""); }}><span className="intel-task-icon">{task.icon}</span><strong>{task.label}</strong><small>{task.description}</small></button>)}</section>

      <section className="intel-stats" aria-label="Backend status">
        <article className="intel-stat"><span>Hotspot API</span><strong>{hotspots.status === "loading" ? "…" : hotspots.status === "ok" ? "Available" : "Unavailable"}</strong><small>{hotspots.status === "ok" ? `${hotspots.count} historical cluster records returned` : hotspots.message}</small></article>
        <article className="intel-stat"><span>Selected locality</span><strong style={{ fontSize: 19 }}>{searchLocation}</strong><small>Location resolution and available station coverage depend on the provider.</small></article>
        <article className="intel-stat"><span>Last successful query</span><strong style={{ fontSize: 16 }}>{checkedAt || "Not run yet"}</strong><small>Results are not refreshed automatically; run an analysis to query the backend.</small></article>
      </section>

      {hotspots.status === "ok" && <div className="intel-note">Hotspot endpoint: {hotspots.message} {hotspots.source ? `Dataset: ${hotspots.source}.` : ""} This endpoint currently reports historical DBSCAN station clusters, not live hotspot detections.</div>}
      {error && <div className="intel-error" role="alert">{error}</div>}

      <section className="intel-result" aria-live="polite">
        <header className="intel-result-head"><div className="intel-result-title"><i/><span>{busy ? "ORIVA is processing the request" : result ? selectedTask.label : "Analysis results"}</span></div><div className="intel-result-meta">{result?.intent && <span className="intel-tag">Intent: {String(result.intent).replaceAll("_", " ")}</span>}{result?.location && <span className="intel-tag">Resolved: {result.location}</span>}{result?.status && <span className="intel-tag">{result.status}</span>}</div></header>
        {busy ? <div className="intel-empty">Sending the request to the backend assistant. The workflow and available tools determine which sources can be queried.</div> : result ? <div className="intel-result-body"><strong style={{ color: "#e9f1ed" }}>{question}</strong>{"\n\n"}{result.answer}</div> : <div className="intel-empty">Choose an analysis above, select a locality, and run it. ORIVA will return the answer and any source information available from the existing backend. Missing data is shown as unavailable rather than replaced with sample values.<br/><br/><button className="intel-button" onClick={() => runQuery(TASKS[0].prompt(location), "aqi")}>Check AQI for {location} ↗</button></div>}
      </section>
    </main>
  );
}
