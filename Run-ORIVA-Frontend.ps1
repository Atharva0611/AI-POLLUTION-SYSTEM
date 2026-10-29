$ErrorActionPreference = "Stop"
$root = "C:\final year project\AI-POLLUTION-SYSTEM-GITHUB"
$front = Join-Path $root "frontend"
Set-Location $front

Write-Host "=== INSTALL FRONTEND DEPENDENCIES ===" -ForegroundColor Cyan
npm install react react-dom lucide-react recharts react-leaflet leaflet
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

if (!(Test-Path "src\App.jsx")) { throw "New Vite frontend not found. Stopping." }

Write-Host "=== 1. CONFIGURE FASTAPI ===" -ForegroundColor Cyan
@'
VITE_API_BASE=http://127.0.0.1:8001
'@ | Set-Content ".env.local" -Encoding utf8

Write-Host "=== 2. CREATE ORIVA APPLICATION ===" -ForegroundColor Cyan
@'
import React, { useCallback, useEffect, useState } from "react";
import {
  Activity, Wind, CloudSun, Gauge, MapPinned, BrainCircuit, ShieldAlert,
  FlaskConical, Lightbulb, MessageSquareText, RefreshCw, Search, Bell,
  ChevronRight, Menu, X, ArrowUpRight, ArrowDownRight, CircleHelp,
  MapPin, Clock3, Database, Wifi, Send, Sparkles, LoaderCircle, ExternalLink
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line, CartesianGrid,
  XAxis, YAxis, Tooltip, BarChart, Bar
} from "recharts";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./index.css";

const API = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8001").replace(/\/$/, "");
const routes = {
  live: ["/api/live/", "/api/live", "/api/current-snapshot/", "/api/current-snapshot"],
  air: ["/api/air-quality/", "/api/air-quality"],
  forecast: ["/api/forecast/", "/api/forecast"],
  hotspots: ["/api/hotspots/", "/api/hotspots"],
  anomalies: ["/api/anomalies/", "/api/anomalies"],
  sources: ["/api/source-analysis/", "/api/source-analysis"],
  recommendations: ["/api/recommendations/", "/api/recommendations"],
  chat: ["/api/chat/", "/api/chat"]
};

const nav = [
  { id: "overview", label: "Overview", group: "WORKSPACE", icon: Gauge },
  { id: "live", label: "Live air quality", icon: Wind },
  { id: "forecast", label: "Forecast & trends", icon: Activity },
  { id: "hotspots", label: "Pollution hotspots", icon: MapPinned },
  { id: "anomalies", label: "Anomaly detection", group: "INTELLIGENCE", icon: ShieldAlert },
  { id: "sources", label: "Source analysis", icon: FlaskConical },
  { id: "recommendations", label: "AI recommendations", icon: Lightbulb },
  { id: "assistant", label: "ORIVA assistant", group: "AI PLATFORM", icon: BrainCircuit }
];

const sampleTrend = [
  { time: "06:00", pm25: 31, pm10: 47 }, { time: "08:00", pm25: 38, pm10: 55 },
  { time: "10:00", pm25: 34, pm10: 51 }, { time: "12:00", pm25: 46, pm10: 67 },
  { time: "14:00", pm25: 41, pm10: 62 }, { time: "16:00", pm25: 52, pm10: 74 },
  { time: "18:00", pm25: 45, pm10: 69 }, { time: "20:00", pm25: 37, pm10: 58 }
];

const sampleForecast = [
  { time: "Now", value: 41 }, { time: "+1h", value: 45 }, { time: "+2h", value: 48 },
  { time: "+3h", value: 43 }, { time: "+4h", value: 39 }, { time: "+5h", value: 36 },
  { time: "+6h", value: 33 }
];

const sampleStations = [
  { name: "Shivajinagar", lat: 18.5308, lon: 73.8475, pm25: 32 },
  { name: "Wagholi", lat: 18.5793, lon: 73.982, pm25: 58 },
  { name: "Hadapsar", lat: 18.5089, lon: 73.926, pm25: 46 },
  { name: "Katraj", lat: 18.4529, lon: 73.867, pm25: 28 },
  { name: "Bhosari", lat: 18.6298, lon: 73.8397, pm25: 63 },
  { name: "Kothrud", lat: 18.5074, lon: 73.8077, pm25: 24 }
];

function pick(obj, keys, fallback = null) {
  for (const key of keys) {
    const value = obj?.[key];
    if (value !== undefined && value !== null && value !== "") return value;
  }
  return fallback;
}
function numberValue(value, fallback = null) {
  const n = Number(value);
  return value !== null && value !== "" && Number.isFinite(n) ? n : fallback;
}
function unwrap(value) {
  if (Array.isArray(value)) return value;
  if (!value || typeof value !== "object") return [];
  for (const k of ["data", "results", "items", "hotspots", "stations", "forecast", "predictions", "anomalies", "recommendations", "records"]) {
    if (Array.isArray(value[k])) return value[k];
  }
  return [];
}
async function requestFirst(paths, options = {}) {
  let lastError;
  for (const path of paths) {
    try {
      const response = await fetch(`${API}${path}`, {
        ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        signal: AbortSignal.timeout(9000)
      });
      if (!response.ok) { lastError = new Error(`${path}: HTTP ${response.status}`); continue; }
      return await response.json();
    } catch (e) { lastError = e; }
  }
  throw lastError || new Error("API endpoint unavailable");
}

function Card({ children, className = "" }) {
  return <section className={`panel ${className}`}>{children}</section>;
}
function SectionTitle({ eyebrow, title, description, action }) {
  return <div className="section-title"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div>;
}
function Pill({ children, tone = "neutral" }) {
  return <span className={`pill pill-${tone}`}><span className="pill-dot" />{children}</span>;
}
function Metric({ label, value, unit, detail, icon: Icon, tone = "blue", loading = false }) {
  return <Card className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-icon ${tone}`}><Icon size={18}/></span></div><div className="metric-value">{loading ? "—" : value ?? "—"}<small>{unit}</small></div><div className="metric-detail">{detail}</div></Card>;
}
function EmptyState({ title = "Waiting for backend data", detail = "Start the FastAPI backend to populate this panel." }) {
  return <div className="empty-state"><Database size={23}/><strong>{title}</strong><span>{detail}</span></div>;
}
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{label}</strong>{payload.map((p) => <div key={p.dataKey}><span style={{color:p.color}}>●</span> {p.name}: {p.value}</div>)}</div>;
}
function MapFocus({ center }) {
  const map = useMap();
  useEffect(() => { map.setView(center, 11); }, [center, map]);
  return null;
}
function HotspotMap({ stations, onSelect }) {
  const [center] = useState([18.5204, 73.8567]);
  return <div className="map-wrap"><MapContainer center={center} zoom={11} scrollWheelZoom className="leaflet-map">
    <MapFocus center={center}/><TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
    {stations.map((s, i) => <CircleMarker key={`${s.name}-${i}`} center={[s.lat, s.lon]} radius={Math.max(7, Math.min(18, (s.pm25 || 20) / 4))} pathOptions={{ color: (s.pm25 || 0) >= 60 ? "#f87171" : (s.pm25 || 0) >= 35 ? "#fbbf24" : "#34d399", fillOpacity: .72 }}>
      <Popup><strong>{s.name}</strong><br/>PM2.5: {s.pm25 ?? "N/A"} µg/m³<br/><button className="text-button" onClick={() => onSelect?.(s)}>View station</button></Popup>
    </CircleMarker>)}
  </MapContainer><div className="map-legend"><span><i className="dot-green"/>Lower</span><span><i className="dot-yellow"/>Elevated</span><span><i className="dot-red"/>High</span></div></div>;
}

export default function App() {
  const [page, setPage] = useState("overview");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState("checking");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [live, setLive] = useState(null);
  const [air, setAir] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [hotspots, setHotspots] = useState(null);
  const [anomalies, setAnomalies] = useState(null);
  const [sources, setSources] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [chatMessages, setChatMessages] = useState([{ role: "assistant", content: "Hello! I’m ORIVA, your environmental intelligence assistant. Ask me about air quality, forecasts, pollution hotspots, or policy recommendations." }]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [selectedStation, setSelectedStation] = useState(null);
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    setBusy(true);
    let successful = 0;
    const load = async (key, setter) => {
      try { const result = await requestFirst(routes[key]); setter(result); successful++; }
      catch { /* show partial results rather than blocking the whole dashboard */ }
    };
    await Promise.all([
      load("live", setLive), load("air", setAir), load("forecast", setForecast),
      load("hotspots", setHotspots), load("anomalies", setAnomalies),
      load("sources", setSources), load("recommendations", setRecommendations)
    ]);
    setApiStatus(successful ? "online" : "offline");
    setLastUpdated(new Date());
    setBusy(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const liveObj = live && typeof live === "object" ? live : {};
  const airObj = air && typeof air === "object" ? air : {};
  const current = { ...airObj, ...liveObj, ...(liveObj.current && typeof liveObj.current === "object" ? liveObj.current : {}) };
  const pm25 = numberValue(pick(current, ["pm25", "pm2_5", "PM2_5", "PM2.5", "pm2_5_ug_m3"]));
  const pm10 = numberValue(pick(current, ["pm10", "PM10"]));
  const aqi = numberValue(pick(current, ["aqi", "AQI", "us_aqi", "india_aqi"]));
  const temp = numberValue(pick(current, ["temperature", "temp", "temperature_c", "temp_c"]));
  const humidity = numberValue(pick(current, ["humidity", "relative_humidity"]));
  const wind = numberValue(pick(current, ["wind_speed", "windSpeed", "wind_speed_kmh"]));
  const location = pick(current, ["location", "city", "station_name", "requested_location"], "Pune, Maharashtra");
  const rawStations = unwrap(hotspots);
  const stations = rawStations.map((s, i) => ({
    ...s,
    name: pick(s, ["station_name", "name", "station", "location"], `Station ${i + 1}`),
    lat: numberValue(pick(s, ["latitude", "lat", "y"])),
    lon: numberValue(pick(s, ["longitude", "lon", "lng", "x"])),
    pm25: numberValue(pick(s, ["mean_pm25", "pm25", "pm2_5", "avg_pm25", "mean_PM2_5"]))
  })).filter(s => s.lat !== null && s.lon !== null);
  const displayedStations = stations.length ? stations : sampleStations;
  const forecastRows = unwrap(forecast).map((x, i) => ({
    time: pick(x, ["time", "timestamp", "datetime", "date"], `T+${i + 1}`),
    value: numberValue(pick(x, ["pm25", "predicted_pm25", "prediction", "predicted", "value", "yhat"]))
  })).filter(x => x.value !== null);
  const trend = forecastRows.length ? forecastRows : sampleForecast;

  const heading = nav.find(n => n.id === page)?.label || "Overview";
  function changePage(id) { setPage(id); setSidebarOpen(false); setNotice(""); }

  async function sendChat(e) {
    e?.preventDefault();
    const question = chatInput.trim();
    if (!question || chatBusy) return;
    setChatInput("");
    setChatMessages(m => [...m, { role: "user", content: question }]);
    setChatBusy(true);
    try {
      let result;
      try {
        result = await requestFirst(routes.chat, { method: "POST", body: JSON.stringify({ message: question, question, query: question }) });
      } catch {
        result = await requestFirst(["/api/chat/"], { method: "POST", body: JSON.stringify({ question }) });
      }
      const answer = pick(result, ["answer", "response", "message", "content", "result", "output"], JSON.stringify(result, null, 2));
      setChatMessages(m => [...m, { role: "assistant", content: typeof answer === "string" ? answer : JSON.stringify(answer) }]);
    } catch {
      setChatMessages(m => [...m, { role: "assistant", content: "I could not reach the ORIVA chat endpoint. Check that FastAPI is running and review its /docs page for the chat request schema." }]);
    } finally { setChatBusy(false); }
  }

  function listRows(data, emptyMessage) {
    const rows = unwrap(data);
    if (!rows.length) return <EmptyState title={emptyMessage || "No records returned"} />;
    return <div className="data-list">{rows.map((row, i) => <div className="data-row" key={i}><div className="row-bullet">{i + 1}</div><div className="row-content"><strong>{pick(row, ["title", "name", "station", "location", "type", "category"], `Record ${i + 1}`)}</strong><p>{pick(row, ["description", "message", "reason", "details", "recommendation", "summary"], JSON.stringify(row))}</p></div><ChevronRight size={17}/></div>)}</div>;
  }

  function chartPanel(title, subtitle, rows, dataKey = "value", color = "#69d8c2") {
    return <Card><div className="panel-heading"><div><h3>{title}</h3><p>{subtitle}</p></div><Pill>API / forecast</Pill></div>{rows.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={rows}><defs><linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={.28}/><stop offset="95%" stopColor={color} stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="#263340"/><XAxis dataKey="time" tick={{fill:"#8293a4",fontSize:11}} axisLine={false} tickLine={false}/><YAxis tick={{fill:"#8293a4",fontSize:11}} axisLine={false} tickLine={false}/><Tooltip content={<ChartTooltip/>}/><Area type="monotone" dataKey={dataKey} name="PM2.5" stroke={color} strokeWidth={2.5} fill="url(#forecastFill)" connectNulls/></AreaChart></ResponsiveContainer></div> : <EmptyState/>}</Card>;
  }

  function renderOverview() {
    return <>
      <div className="welcome-row"><div><div className="eyebrow">ENVIRONMENTAL INTELLIGENCE PLATFORM</div><h2>Good day, <span className="text-accent">let’s protect the air.</span></h2><p>Monitor conditions, understand emerging risks, and turn environmental data into action.</p></div><button className="button-secondary" onClick={refresh} disabled={busy}><RefreshCw size={15} className={busy ? "spin" : ""}/>{busy ? "Refreshing" : "Refresh data"}</button></div>
      <div className="metrics-grid">
        <Metric label="Air Quality Index" value={aqi ?? "—"} unit={aqi !== null ? "AQI" : ""} detail={aqi !== null ? (aqi <= 50 ? "Good" : aqi <= 100 ? "Moderate / satisfactory" : "Elevated pollution") : "Awaiting API response"} icon={Gauge} tone="green"/>
        <Metric label="PM2.5 concentration" value={pm25 ?? "—"} unit={pm25 !== null ? "µg/m³" : ""} detail="Fine particulate matter" icon={Wind} tone="blue"/>
        <Metric label="PM10 concentration" value={pm10 ?? "—"} unit={pm10 !== null ? "µg/m³" : ""} detail="Coarse particulate matter" icon={Activity} tone="purple"/>
        <Metric label="Temperature" value={temp ?? "—"} unit={temp !== null ? "°C" : ""} detail={humidity !== null ? `Humidity ${humidity}%` : "Environmental conditions"} icon={CloudSun} tone="orange"/>
      </div>
      <div className="content-grid two-one">
        <Card><div className="panel-heading"><div><h3>Pollution trend</h3><p>Measured values or fallback illustration</p></div><Pill tone={apiStatus === "online" ? "green" : "neutral"}>{apiStatus === "online" ? "Connected" : "Illustrative"}</Pill></div>
          <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><LineChart data={sampleTrend}><CartesianGrid strokeDasharray="3 3" stroke="#263340"/><XAxis dataKey="time" tick={{fill:"#8293a4",fontSize:11}} axisLine={false} tickLine={false}/><YAxis tick={{fill:"#8293a4",fontSize:11}} axisLine={false} tickLine={false}/><Tooltip content={<ChartTooltip/>}/><Line type="monotone" dataKey="pm25" name="PM2.5" stroke="#69d8c2" strokeWidth={2.5} dot={false}/><Line type="monotone" dataKey="pm10" name="PM10" stroke="#9a8df5" strokeWidth={2} dot={false}/></LineChart></ResponsiveContainer></div>
          <div className="chart-legend"><span><i style={{background:"#69d8c2"}}/>PM2.5</span><span><i style={{background:"#9a8df5"}}/>PM10</span></div>
        </Card>
        <Card><div className="panel-heading"><div><h3>Environmental status</h3><p>{location}</p></div><CloudSun size={20} className="muted"/></div>
          <div className="weather-stack"><div className="weather-big"><CloudSun size={32}/><strong>{temp !== null ? `${temp}°C` : "—"}</strong><span>Temperature</span></div><div className="weather-stats"><div><span>Humidity</span><strong>{humidity !== null ? `${humidity}%` : "—"}</strong></div><div><span>Wind speed</span><strong>{wind !== null ? `${wind} km/h` : "—"}</strong></div><div><span>Location</span><strong>{String(location)}</strong></div></div></div>
          <button className="full-link" onClick={() => changePage("live")}>View live environment <ArrowUpRight size={16}/></button>
        </Card>
      </div>
      <div className="content-grid two-one">
        <Card><div className="panel-heading"><div><h3>Pollution hotspot map</h3><p>Available station coordinates from the hotspot API</p></div><button className="text-button" onClick={() => changePage("hotspots")}>Explore map <ArrowUpRight size={14}/></button></div><HotspotMap stations={displayedStations} onSelect={setSelectedStation}/>{selectedStation && <div className="selected-note"><MapPin size={14}/>{selectedStation.name}: PM2.5 {selectedStation.pm25 ?? "N/A"} µg/m³</div>}</Card>
        <Card><div className="panel-heading"><div><h3>Intelligence centre</h3><p>Quick access to analysis tools</p></div><Sparkles size={18} className="accent"/></div><div className="quick-actions">{nav.filter(n => ["forecast","anomalies","sources","recommendations","assistant"].includes(n.id)).map(item => <button className="quick-action" key={item.id} onClick={() => changePage(item.id)}><span className="quick-icon"><item.icon size={17}/></span><span>{item.label}</span><ChevronRight size={15}/></button>)}</div></Card>
      </div>
      <Card><div className="panel-heading"><div><h3>System status</h3><p>Connection to the existing ORIVA FastAPI services</p></div><Pill tone={apiStatus === "online" ? "green" : "red"}>{apiStatus === "online" ? "API reachable" : "API unavailable"}</Pill></div><div className="status-strip"><div><span className="status-light" style={{background:apiStatus === "online" ? "#53d6a3" : "#f87171"}}/>FastAPI endpoint<strong>{API}</strong></div><div><Database size={17}/><span>Data status</span><strong>{successfulText(apiStatus)}</strong></div><div><Clock3 size={17}/><span>Last checked</span><strong>{lastUpdated ? lastUpdated.toLocaleTimeString() : "Not checked"}</strong></div></div>{apiStatus !== "online" && <div className="inline-warning"><CircleHelp size={17}/>No API endpoint responded. Start FastAPI and confirm the configured port. Dashboard charts labelled illustrative are not live measurements.</div>}</Card>
    </>;
  }

  function successfulText(status) { return status === "online" ? "Some endpoints responding" : "Waiting for connection"; }

  function renderPage() {
    if (page === "overview") return renderOverview();
    if (page === "live") return <>
      <SectionTitle eyebrow="REAL-TIME MONITORING" title="Live air quality" description="Current environmental readings from the connected ORIVA services." action={<button className="button-secondary" onClick={refresh}><RefreshCw size={15}/>Refresh</button>}/>
      <div className="metrics-grid"><Metric label="AQI" value={aqi ?? "—"} unit="AQI" detail="Reported index" icon={Gauge}/><Metric label="PM2.5" value={pm25 ?? "—"} unit="µg/m³" detail="Fine particles" icon={Wind}/><Metric label="PM10" value={pm10 ?? "—"} unit="µg/m³" detail="Coarse particles" icon={Activity}/><Metric label="Wind speed" value={wind ?? "—"} unit={wind !== null ? "km/h" : ""} detail="Reported wind speed" icon={CloudSun}/></div>
      <div className="content-grid two-one"><Card><div className="panel-heading"><div><h3>Current API payload</h3><p>Returned values for inspection</p></div><Pill tone={live || air ? "green" : "neutral"}>{live || air ? "Data received" : "No data"}</Pill></div>{live || air ? <pre className="json-view">{JSON.stringify({live, air}, null, 2)}</pre> : <EmptyState/>}</Card><Card><h3>Data provenance</h3><p className="muted">Values appear only when returned by the API. This page does not fabricate live measurements.</p><div className="data-list"><div className="data-row"><Wifi size={18}/><div className="row-content"><strong>API connection</strong><p>{apiStatus === "online" ? "At least one endpoint responded." : "No configured endpoint has responded."}</p></div></div><div className="data-row"><MapPin size={18}/><div className="row-content"><strong>Requested location</strong><p>{String(location)}</p></div></div></div></Card></div>
    </>;
    if (page === "forecast") return <>
      <SectionTitle eyebrow="PREDICTIVE ANALYTICS" title="Forecast & trends" description="Explore predictions returned by the ORIVA forecasting service." action={<button className="button-secondary" onClick={refresh}><RefreshCw size={15}/>Reload forecast</button>}/>
      {chartPanel("PM2.5 forecast","Prediction values returned by the API",trend)}
      <Card><div className="panel-heading"><div><h3>Forecast response</h3><p>Raw response for transparent model inspection</p></div></div>{forecast ? <pre className="json-view">{JSON.stringify(forecast,null,2)}</pre> : <EmptyState/>}</Card>
    </>;
    if (page === "hotspots") return <>
      <SectionTitle eyebrow="SPATIAL INTELLIGENCE" title="Pollution hotspots" description="Explore available station coordinates and returned hotspot classifications." action={<button className="button-secondary" onClick={refresh}><RefreshCw size={15}/>Refresh</button>}/>
      <Card><div className="panel-heading"><div><h3>Station distribution</h3><p>{stations.length ? `${stations.length} geolocated records from API` : "Sample Pune markers are illustrative only"}</p></div><Pill>{stations.length ? "API data" : "Demo map"}</Pill></div><HotspotMap stations={displayedStations} onSelect={setSelectedStation}/>{selectedStation && <div className="selected-note"><MapPin size={14}/>{selectedStation.name} — PM2.5 {selectedStation.pm25 ?? "N/A"} µg/m³</div>}</Card>
      <Card><div className="panel-heading"><div><h3>Hotspot records</h3><p>Backend response, if available</p></div></div>{hotspots ? <pre className="json-view">{JSON.stringify(hotspots,null,2)}</pre> : <EmptyState/>}</Card>
    </>;
    if (page === "anomalies") return <><SectionTitle eyebrow="EARLY WARNING" title="Anomaly detection" description="Review anomaly flags and unusual pollution events returned by the backend."/><Card><div className="panel-heading"><div><h3>Detected anomalies</h3><p>API results</p></div><Pill tone={anomalies ? "green" : "neutral"}>{anomalies ? "Response received" : "Awaiting data"}</Pill></div>{listRows(anomalies,"No anomaly records available")}</Card><Card><h3>Raw anomaly response</h3>{anomalies ? <pre className="json-view">{JSON.stringify(anomalies,null,2)}</pre> : <EmptyState/>}</Card></>;
    if (page === "sources") return <><SectionTitle eyebrow="POLLUTION ATTRIBUTION" title="Source analysis" description="Inspect source attribution and diagnostic results from ORIVA."/><Card><div className="panel-heading"><div><h3>Source analysis results</h3><p>Based on the configured source-analysis API</p></div><FlaskConical size={19} className="accent"/></div>{listRows(sources,"No source analysis results available")}</Card><Card><h3>Raw source response</h3>{sources ? <pre className="json-view">{JSON.stringify(sources,null,2)}</pre> : <EmptyState/>}</Card></>;
    if (page === "recommendations") return <><SectionTitle eyebrow="DECISION SUPPORT" title="AI recommendations" description="Review actions returned by the ORIVA recommendation service."/><Card><div className="panel-heading"><div><h3>Recommended actions</h3><p>Recommendations from the backend response</p></div><Lightbulb size={19} className="accent"/></div>{listRows(recommendations,"No recommendations available")}</Card><Card><h3>Raw recommendations response</h3>{recommendations ? <pre className="json-view">{JSON.stringify(recommendations,null,2)}</pre> : <EmptyState/>}</Card></>;
    return <><SectionTitle eyebrow="CONVERSATIONAL INTELLIGENCE" title="ORIVA assistant" description="Ask questions about air quality, forecasts, pollution sources, and environmental policy."/><Card className="assistant-panel"><div className="assistant-heading"><span className="assistant-avatar"><BrainCircuit size={22}/></span><div><strong>ORIVA Intelligence</strong><p>Connected to your configured chat API</p></div><span className={`connection-dot ${apiStatus === "online" ? "connected" : ""}`}/></div><div className="chat-messages">{chatMessages.map((m,i)=><div key={i} className={`chat-message ${m.role}`}><span className="chat-avatar">{m.role === "assistant" ? <Sparkles size={16}/> : "Y"}</span><div className="chat-bubble">{m.content}</div></div>)}{chatBusy && <div className="chat-message assistant"><span className="chat-avatar"><Sparkles size={16}/></span><div className="chat-bubble"><LoaderCircle className="spin" size={17}/> Thinking…</div></div>}</div><form className="chat-form" onSubmit={sendChat}><input value={chatInput} onChange={e=>setChatInput(e.target.value)} placeholder="Ask ORIVA about air quality…" aria-label="Message ORIVA"/><button type="submit" disabled={chatBusy || !chatInput.trim()}><Send size={17}/>Send</button></form><div className="chat-disclaimer">Answers depend on the configured backend, its data sources, and available model integrations.</div></Card></>;
  }

  const filteredNav = nav.filter(item => item.label.toLowerCase().includes(search.toLowerCase()));
  return <div className="app-shell">
    {sidebarOpen && <button className="sidebar-scrim" onClick={()=>setSidebarOpen(false)} aria-label="Close navigation"/>}
    <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-symbol"><Activity size={23}/></div><div><strong>ORIVA<span> AI</span></strong><small>ENVIRONMENTAL INTELLIGENCE</small></div><button className="mobile-close" onClick={()=>setSidebarOpen(false)}><X size={19}/></button></div>
      <div className="workspace"><div className="workspace-icon"><Wind size={18}/></div><div><strong>Air Intelligence</strong><span>Pollution monitoring</span></div><ChevronRight size={15}/></div>
      <div className="sidebar-search"><Search size={15}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Find a page…"/></div>
      <nav className="navigation">{filteredNav.map((item,i)=><React.Fragment key={item.id}>{item.group && <div className="nav-group">{item.group}</div>}<button onClick={()=>changePage(item.id)} className={`nav-item ${page === item.id ? "active" : ""}`}><item.icon size={18}/><span>{item.label}</span>{item.id === "assistant" && <span className="new-tag">AI</span>}</button></React.Fragment>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><Sparkles size={18}/></div><strong>Environmental insights</strong><p>Turn pollution data into better decisions.</p><button onClick={()=>changePage("assistant")}>Ask ORIVA <ArrowUpRight size={14}/></button></div><div className="sidebar-footer"><span className={`status-light ${apiStatus === "online" ? "" : "offline"}`}/><span>{apiStatus === "online" ? "API connected" : "API not connected"}</span><span className="version">v1.0</span></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="topbar-left"><button className="mobile-menu" onClick={()=>setSidebarOpen(true)}><Menu size={21}/></button><div className="breadcrumbs"><span>ORIVA</span><ChevronRight size={14}/><strong>{heading}</strong></div></div><div className="topbar-right"><div className="location-chip"><MapPin size={14}/>{String(location)}</div><div className={`api-chip ${apiStatus}`}><span className="status-light"/>{apiStatus === "online" ? "API online" : apiStatus === "checking" ? "Checking API" : "API offline"}</div><button className="icon-button" onClick={refresh} title="Refresh data"><RefreshCw size={17} className={busy ? "spin" : ""}/></button><button className="icon-button" onClick={()=>setNotice(notice ? "" : "ORIVA dashboard notifications: API connectivity and data availability are shown in the system status panel.")} title="Notifications"><Bell size={17}/></button></div></header>
      {notice && <div className="notice-bar">{notice}<button onClick={()=>setNotice("")}><X size={15}/></button></div>}
      <div className="page-content">{renderPage()}<footer className="app-footer"><span>ORIVA AI · Environmental Intelligence</span><span>Data displayed only when returned by configured services</span></footer></div>
    </main>
  </div>;
}
'@ | Set-Content "src\App.jsx" -Encoding utf8

Write-Host "=== 3. CREATE STYLES ===" -ForegroundColor Cyan
@'
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{font-family:'DM Sans',sans-serif;color:#e8eef4;background:#0a1017;font-synthesis:none;text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased;font-optical-sizing:auto;font-weight:400;--bg:#0a1017;--panel:#111a24;--panel2:#151f2a;--border:#24313e;--muted:#8595a5;--text:#e8eef4;--accent:#69d8c2;--accent2:#9a8df5}
*{box-sizing:border-box}body{margin:0;min-width:320px;min-height:100vh;background:var(--bg)}button,input{font:inherit}button{cursor:pointer}button:disabled{opacity:.55;cursor:not-allowed}button:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}h1,h2,h3,p{margin-top:0}h1,h2,h3,strong{font-family:Manrope,'DM Sans',sans-serif}h2{font-size:25px;letter-spacing:-.8px;margin:6px 0 8px}h3{font-size:14px;margin:0;font-weight:750;letter-spacing:-.15px}p{color:var(--muted);font-size:12px;line-height:1.65;margin:6px 0 0}.app-shell{min-height:100vh}.sidebar{width:258px;position:fixed;inset:0 auto 0 0;background:#0d151e;border-right:1px solid #202c38;padding:23px 15px 15px;display:flex;flex-direction:column;z-index:30}.brand{display:flex;align-items:center;gap:11px;padding:0 7px 25px}.brand-symbol{width:41px;height:41px;border-radius:13px;background:linear-gradient(135deg,#65d9c1,#35a99e);color:#08211f;display:grid;place-items:center;box-shadow:0 5px 24px #4ac9b322}.brand strong{font-size:19px;letter-spacing:.5px;display:block}.brand strong span{color:var(--accent)}.brand small{font-size:8px;letter-spacing:1.3px;color:#8fa2b2;display:block;margin-top:3px}.mobile-close{display:none;margin-left:auto;background:none;color:white;border:0}.workspace{background:#131e28;border:1px solid #293745;border-radius:12px;padding:11px;display:flex;align-items:center;gap:10px;margin-bottom:17px}.workspace-icon{width:34px;height:34px;border-radius:10px;background:#1d373a;color:var(--accent);display:grid;place-items:center}.workspace>div:nth-child(2){flex:1}.workspace strong{display:block;font-size:11px}.workspace span{display:block;font-size:10px;color:var(--muted);margin-top:4px}.workspace>svg{color:#7b8d9c}.sidebar-search{display:flex;align-items:center;gap:8px;border:1px solid #273541;background:#111a23;border-radius:9px;padding:10px;color:#8194a5;margin-bottom:20px}.sidebar-search input{border:0;outline:0;background:transparent;color:var(--text);min-width:0;width:100%;font-size:11px}.navigation{overflow:auto;flex:1}.nav-group{font-size:9px;letter-spacing:1.3px;font-weight:700;color:#607385;padding:11px 10px 9px}.nav-item{display:flex;align-items:center;gap:11px;width:100%;border:0;background:transparent;color:#9baaba;padding:11px 10px;border-radius:9px;text-align:left;font-size:11px;margin:2px 0;transition:.15s}.nav-item span:nth-child(2){flex:1}.nav-item:hover{background:#17232d;color:white}.nav-item.active{color:#7fe3cf;background:linear-gradient(90deg,#1b3938,#172b30);box-shadow:inset 2px 0 #69d8c2}.nav-item.active svg{color:var(--accent)}.new-tag{font-size:8px;background:#3c315f;color:#c4baff;padding:3px 5px;border-radius:5px}.sidebar-bottom{padding-top:12px}.help-card{background:linear-gradient(145deg,#162a30,#151f2a);border:1px solid #29433f;border-radius:12px;padding:14px}.help-icon{color:var(--accent);margin-bottom:9px}.help-card strong{font-size:11px}.help-card p{font-size:10px;margin:6px 0 12px}.help-card button{background:none;border:0;padding:0;color:var(--accent);font-size:10px;display:flex;gap:5px;align-items:center}.sidebar-footer{display:flex;align-items:center;gap:7px;color:#8799a9;font-size:10px;padding:16px 5px 3px}.version{margin-left:auto;color:#596b7c}.status-light{width:7px;height:7px;border-radius:50%;display:inline-block;background:#f87171;flex-shrink:0}.status-light.offline{background:#f87171}.main-area{margin-left:258px;min-height:100vh}.topbar{height:70px;border-bottom:1px solid #202c38;background:#0c131b;display:flex;align-items:center;justify-content:space-between;padding:0 32px;position:sticky;top:0;z-index:20}.topbar-left,.topbar-right,.breadcrumbs{display:flex;align-items:center;gap:12px}.breadcrumbs{font-size:11px;color:#788a9a}.breadcrumbs strong{color:#dce5ed;font-size:11px}.topbar-right{gap:10px}.location-chip,.api-chip{display:flex;align-items:center;gap:7px;padding:8px 10px;border:1px solid #273542;border-radius:8px;font-size:10px;color:#a6b5c3;white-space:nowrap}.location-chip svg{color:var(--accent)}.api-chip{border:0;background:#1a222a}.api-chip.online{color:#80e1b9}.api-chip.online .status-light{background:#53d6a3}.icon-button,.mobile-menu{width:34px;height:34px;display:grid;place-items:center;border:1px solid #263541;border-radius:9px;background:#131c25;color:#9babb9}.icon-button:hover{color:var(--accent);border-color:#47776f}.mobile-menu{display:none}.page-content{padding:29px 32px 20px;max-width:1600px;margin:0 auto}.welcome-row{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:23px}.welcome-row h2{font-size:26px}.welcome-row p{font-size:12px;max-width:600px}.eyebrow{font-size:9px;font-weight:700;letter-spacing:1.5px;color:#76cbbd}.text-accent,.accent{color:var(--accent)}.button-secondary{border:1px solid #2a3b48;background:#141e28;color:#d5e0e8;border-radius:9px;padding:10px 13px;display:inline-flex;align-items:center;gap:8px;font-size:11px;white-space:nowrap}.button-secondary:hover{border-color:#5a9e91;color:var(--accent)}.metrics-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:16px}.panel{background:linear-gradient(145deg,#121c26,#101821);border:1px solid #25323e;border-radius:13px;padding:19px;min-width:0;margin-bottom:16px}.metric-card{padding:17px 18px;position:relative;overflow:hidden}.metric-top{display:flex;align-items:center;justify-content:space-between;gap:8px;color:#a0b0bf;font-size:10px}.metric-icon{width:34px;height:34px;border-radius:10px;display:grid;place-items:center}.metric-icon.green{background:#19372f;color:#70e0b5}.metric-icon.blue{background:#1c3046;color:#79b8ff}.metric-icon.purple{background:#2a2444;color:#b8a9ff}.metric-icon.orange{background:#3b2c23;color:#ffbc83}.metric-value{font-family:Manrope,sans-serif;font-size:30px;font-weight:750;letter-spacing:-1.3px;margin:13px 0 7px;color:#f0f5f8}.metric-value small{font-family:'DM Sans',sans-serif;font-size:10px;font-weight:500;color:#8294a4;letter-spacing:0;margin-left:6px}.metric-detail{font-size:10px;color:#8496a5;min-height:14px}.content-grid{display:grid;gap:16px;margin-bottom:0}.two-one{grid-template-columns:minmax(0,1.65fr) minmax(260px,1fr)}.panel-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:18px}.panel-heading p{font-size:10px;margin-top:5px}.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid #34404b;border-radius:20px;padding:5px 8px;color:#aab8c5;font-size:9px;white-space:nowrap}.pill-dot{width:5px;height:5px;border-radius:50%;background:#9aa9b7}.pill-green{color:#82e2bb;border-color:#28513f;background:#162c27}.pill-green .pill-dot{background:#64dda9}.pill-red{color:#ff9e9e;border-color:#583439;background:#2d1c22}.chart-area{height:240px;width:100%}.chart-legend{display:flex;gap:17px;color:#9babb9;font-size:10px;padding-top:6px}.chart-legend span{display:flex;align-items:center;gap:6px}.chart-legend i{width:7px;height:7px;border-radius:50%}.chart-tooltip{background:#18242e;border:1px solid #35434f;padding:10px 12px;border-radius:9px;font-size:11px;color:#e9eff4;box-shadow:0 10px 25px #0004}.chart-tooltip strong{display:block;margin-bottom:5px}.weather-stack{display:flex;gap:15px;align-items:center;min-height:145px}.weather-big{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:100px;color:#f7c87c}.weather-big strong{font-size:26px;color:#f1f5f7}.weather-big span{font-size:10px;color:var(--muted)}.weather-stats{flex:1;border-left:1px solid #293742;padding-left:16px;display:grid;gap:13px}.weather-stats div{display:flex;flex-direction:column;gap:4px}.weather-stats span{font-size:10px;color:#8fa0ae}.weather-stats strong{font-size:12px;overflow-wrap:anywhere}.full-link{width:100%;display:flex;justify-content:space-between;align-items:center;background:none;border:0;border-top:1px solid #283641;padding:14px 0 0;margin-top:8px;color:var(--accent);font-size:10px}.quick-actions{display:grid;gap:4px}.quick-action{display:flex;align-items:center;gap:10px;padding:10px 0;background:transparent;border:0;color:#bdc8d1;text-align:left;font-size:10px;border-bottom:1px solid #202e39}.quick-action:last-child{border-bottom:0}.quick-action>span:nth-child(2){flex:1}.quick-icon{color:#81d8c5;width:30px;height:30px;border-radius:9px;display:grid;place-items:center;background:#1b302f}.quick-action>svg{color:#758898}.map-wrap{height:300px;position:relative;border:1px solid #293843;border-radius:10px;overflow:hidden;background:#101923}.leaflet-map{height:100%;width:100%;background:#15202a}.leaflet-container{font-family:'DM Sans',sans-serif}.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:#14202b;color:#edf4f6}.leaflet-popup-content{font-size:11px;line-height:1.7}.leaflet-popup-content button{margin-top:5px}.map-legend{position:absolute;z-index:500;bottom:12px;left:12px;display:flex;gap:10px;background:#0d1720ed;border:1px solid #31404a;border-radius:8px;padding:9px 11px;font-size:9px;color:#d2dde4}.map-legend span{display:flex;align-items:center;gap:5px}.map-legend i{width:7px;height:7px;border-radius:50%}.dot-green{background:#34d399}.dot-yellow{background:#fbbf24}.dot-red{background:#f87171}.selected-note{display:flex;gap:7px;align-items:center;padding-top:12px;font-size:10px;color:var(--accent)}.status-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.status-strip>div{display:grid;grid-template-columns:16px 1fr;gap:5px 8px;align-items:center;border:1px solid #293641;background:#121d27;border-radius:9px;padding:12px;color:#8fa0ae;font-size:10px;min-width:0}.status-strip strong{grid-column:2;font-size:10px;color:#d8e1e8;overflow-wrap:anywhere}.status-strip .status-light{grid-column:1}.inline-warning{margin-top:13px;display:flex;align-items:flex-start;gap:9px;background:#322a1c;color:#f4d69b;border:1px solid #51412b;border-radius:9px;padding:12px;font-size:10px;line-height:1.6}.inline-warning svg{flex-shrink:0}.section-title{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:23px}.section-title h2{margin-top:8px}.section-title p{font-size:12px}.empty-state{min-height:115px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:9px;color:#718595;text-align:center;padding:18px}.empty-state strong{font-size:11px;color:#c6d2dc}.empty-state span{font-size:10px;max-width:320px;line-height:1.6}.muted{color:var(--muted)}.json-view{white-space:pre-wrap;word-break:break-word;overflow:auto;max-height:420px;background:#0b1219;border:1px solid #263540;border-radius:9px;padding:14px;color:#a8ddcf;font:11px/1.65 Consolas,monospace}.data-list{display:grid}.data-row{display:flex;align-items:flex-start;gap:12px;padding:13px 0;border-bottom:1px solid #25313b;color:#8496a6}.data-row:last-child{border-bottom:0}.row-bullet{width:26px;height:26px;flex-shrink:0;border-radius:8px;display:grid;place-items:center;background:#1a302f;color:var(--accent);font-size:10px}.row-content{flex:1;min-width:0}.row-content strong{font-size:11px;color:#e0e8ee}.row-content p{overflow-wrap:anywhere}.data-row>svg{margin-top:4px}.text-button{display:inline-flex;align-items:center;gap:5px;border:0;background:transparent;color:var(--accent);font-size:10px}.assistant-panel{max-width:1000px;margin:0 auto}.assistant-heading{display:flex;align-items:center;gap:12px;border-bottom:1px solid #27343f;padding-bottom:17px}.assistant-avatar{width:42px;height:42px;border-radius:13px;display:grid;place-items:center;background:#1d3a38;color:var(--accent)}.assistant-heading strong{font-size:13px}.assistant-heading p{font-size:10px}.connection-dot{margin-left:auto;width:8px;height:8px;background:#f87171;border-radius:50%}.connection-dot.connected{background:#5fe0a9}.chat-messages{display:flex;flex-direction:column;gap:17px;min-height:260px;max-height:520px;overflow:auto;padding:23px 0}.chat-message{display:flex;align-items:flex-start;gap:10px}.chat-message.user{flex-direction:row-reverse}.chat-avatar{width:30px;height:30px;flex-shrink:0;border-radius:10px;display:grid;place-items:center;background:#1d3434;color:var(--accent);font-size:11px}.chat-message.user .chat-avatar{background:#2b3150;color:#c1b8ff}.chat-bubble{max-width:82%;white-space:pre-wrap;overflow-wrap:anywhere;background:#17232d;border:1px solid #2a3944;border-radius:4px 12px 12px 12px;padding:12px 14px;font-size:11px;line-height:1.7;color:#dce5eb}.chat-message.user .chat-bubble{background:#213333;border-color:#31514d;border-radius:12px 4px 12px 12px}.chat-form{display:flex;gap:9px;padding-top:14px;border-top:1px solid #283641}.chat-form input{flex:1;min-width:0;background:#0d151d;border:1px solid #2a3945;border-radius:9px;padding:13px;color:#e9eff4;font-size:11px}.chat-form button{display:flex;align-items:center;justify-content:center;gap:7px;background:#67d4be;color:#08211f;border:0;border-radius:9px;padding:0 17px;font-weight:700;font-size:11px}.chat-disclaimer{font-size:9px;color:#748696;margin-top:11px}.app-footer{display:flex;justify-content:space-between;gap:15px;padding:14px 2px;color:#627687;font-size:9px}.notice-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 32px;background:#1b2b32;color:#bcebe0;font-size:11px}.notice-bar button{background:none;border:0;color:inherit}.mobile-menu{display:none}.sidebar-scrim{display:none}.spin{animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}@media(min-width:1500px){.page-content{padding-top:36px}.metrics-grid{gap:18px}.panel{padding:22px}.chart-area{height:275px}}@media(max-width:1150px){.sidebar{width:230px}.main-area{margin-left:230px}.topbar{padding:0 20px}.page-content{padding:23px 20px}.metrics-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.two-one{grid-template-columns:minmax(0,1fr)}.location-chip{display:none}}@media(max-width:720px){.sidebar{transform:translateX(-100%);transition:transform .22s;width:270px}.sidebar.sidebar-open{transform:translateX(0)}.sidebar-scrim{display:block;position:fixed;inset:0;background:#0009;border:0;z-index:25}.mobile-close,.mobile-menu{display:grid}.main-area{margin-left:0}.topbar{height:60px;padding:0 14px}.topbar-right{gap:6px}.topbar-right .icon-button{display:none}.breadcrumbs{gap:6px}.api-chip{font-size:9px;padding:7px}.page-content{padding:22px 14px}.welcome-row{align-items:flex-start;flex-direction:column}.welcome-row h2{font-size:22px}.metrics-grid{gap:9px}.metric-card{padding:13px}.metric-value{font-size:25px}.metric-top{font-size:9px}.metric-icon{width:30px;height:30px}.panel{padding:14px;margin-bottom:12px}.content-grid{gap:0}.chart-area{height:215px}.section-title{align-items:flex-start;flex-direction:column}.section-title h2{font-size:22px}.map-wrap{height:290px}.status-strip{grid-template-columns:1fr}.weather-stack{gap:10px}.weather-big{min-width:85px}.weather-stats{padding-left:12px}.app-footer{flex-direction:column;gap:5px}.chat-bubble{max-width:88%}.chat-form button{padding:0 12px}.notice-bar{padding:10px 14px}}@media(max-width:380px){.metrics-grid{grid-template-columns:1fr}.metric-card{padding:15px}.topbar-right .api-chip{max-width:104px;overflow:hidden}.breadcrumbs{font-size:10px}}
'@ | Set-Content "src\index.css" -Encoding utf8

Write-Host "=== 4. ENSURE ENTRY POINT ===" -ForegroundColor Cyan
@'
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode><App /></React.StrictMode>
);
'@ | Set-Content "src\main.jsx" -Encoding utf8

Write-Host "=== 5. BUILD COMPLETE FRONTEND ===" -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) { throw "Build failed. Paste the full error output." }

Write-Host "`n=== FRONTEND BUILD SUCCESS ===" -ForegroundColor Green
Write-Host "Starting frontend at http://127.0.0.1:5173" -ForegroundColor Green
npm run dev