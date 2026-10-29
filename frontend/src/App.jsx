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

const API = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8003").replace(/\/$/, "");
const routes = {
  live: ["/api/live/air-quality"],
  air: ["/api/pollution/current"],
  locations: ["/api/air-quality/locations"],
  forecast: ["/api/forecast/universal"],
  hotspots: ["/api/hotspots/"],
  anomalies: ["/api/anomalies/"],
  sources: ["/api/source-analysis/"],
  recommendations: ["/api/recommendations/"],
  chat: ["/api/chat"]
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
function formatLocation(loc, fallback = "Pune, Maharashtra") {
  if (!loc) return fallback;
  if (typeof loc === "string") return loc;
  if (typeof loc === "object") {
    return loc.display_name || loc.city || loc.station_name || loc.name || loc.requested_location || loc.weatherapi_location || fallback;
  }
  return String(loc);
}
function numberValue(value, fallback = null) {
  const n = Number(value);
  return value !== null && value !== "" && Number.isFinite(n) ? n : fallback;
}
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("Dashboard caught error:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="panel" style={{ margin: "40px auto", maxWidth: 600, padding: 24, textAlign: "center" }}>
          <h2>Dashboard encountered an issue</h2>
          <p style={{ color: "#f87171", margin: "12px 0" }}>{this.state.error?.message || "Unknown error"}</p>
          <button className="button-secondary" onClick={() => this.setState({ hasError: false })}>Try again</button>
        </div>
      );
    }
    return this.props.children;
  }
}
function unwrap(value) {
  if (Array.isArray(value)) return value;
  if (!value || typeof value !== "object") return [];
  for (const k of ["data", "results", "items", "hotspots", "stations", "forecast", "predictions", "hourly_context", "anomalies", "recommendations", "records"]) {
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
  return <Card className="metric-card"><div className="metric-top"><span>{label}</span><span className={`metric-icon ${tone}`}><Icon size={18}/></span></div><div className="metric-value">{loading ? "-" : value ?? "-"}<small>{unit}</small></div><div className="metric-detail">{detail}</div></Card>;
}
function EmptyState({ title = "Waiting for backend data", detail = "Start the FastAPI backend to populate this panel." }) {
  return <div className="empty-state"><Database size={23}/><strong>{title}</strong><span>{detail}</span></div>;
}
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{label}</strong>{payload.map((p) => <div key={p.dataKey}><span style={{color:p.color}}>ÃƒÂ¢Ã¢â‚¬â€Ã‚Â</span> {p.name}: {p.value}</div>)}</div>;
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
      <Popup><strong>{s.name}</strong><br/>PM2.5: {s.pm25 ?? "N/A"} Ã‚Âµg/mÃ‚Â³<br/><button className="text-button" onClick={() => onSelect?.(s)}>View station</button></Popup>
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
  const [locationInput, setLocationInput] = useState("Pune, Maharashtra");
  const [selectedLocation, setSelectedLocation] = useState("Pune, Maharashtra");
  const [live, setLive] = useState(null);
  const [air, setAir] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [hotspots, setHotspots] = useState(null);
  const [anomalies, setAnomalies] = useState(null);
  const [sources, setSources] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [chatMessages, setChatMessages] = useState([{ role: "assistant", content: "Hello! I'm ORIVA, your environmental intelligence assistant. Ask me about air quality, forecasts, pollution hotspots, or policy recommendations." }]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [selectedStation, setSelectedStation] = useState(null);
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async (targetLocation = selectedLocation) => {
    if (!targetLocation?.trim()) return;

    setBusy(true);
    setLive(null);
    setAir(null);
    setForecast(null);
    let successful = 0;

    const withLocation = (paths) => paths.map(path =>
      `${path}${path.includes("?") ? "&" : "?"}location=${encodeURIComponent(targetLocation)}`
    );

    const load = async (key, setter, paths = routes[key]) => {
      try {
        const result = await requestFirst(paths);
        setter(result);
        successful++;
        return result;
      } catch (error) {
        console.error(`ORIVA ${key} request failed:`, error);
        return null;
      }
    };

    try {
      // Resolve the searched location first.
      const liveResult = await load("live", setLive, withLocation(routes.live));

      const airPaths = [
        `/api/pollution/current?location=${encodeURIComponent(targetLocation)}`
      ];
      await load("air", setAir, airPaths);
      const resolved = liveResult?.location;
      const lat = Number(resolved?.latitude);
      const lon = Number(resolved?.longitude);

      // Reuse live coordinates for the forecast when available.
      const forecastPaths = withLocation(routes.forecast).map(path => {
        if (!Number.isFinite(lat) || !Number.isFinite(lon)) return path;
        return `${path}&latitude=${encodeURIComponent(lat)}&longitude=${encodeURIComponent(lon)}`;
      });

      await Promise.all([
        load("forecast", setForecast, forecastPaths),
        load("hotspots", setHotspots),
        load("anomalies", setAnomalies),
        load("sources", setSources),
        load("recommendations", setRecommendations)
      ]);

      setApiStatus(successful ? "online" : "offline");
      setLastUpdated(new Date());
    } finally {
      setBusy(false);
    }
  }, [selectedLocation]);

  function submitLocation(e) {
    e.preventDefault();
    const value = locationInput.trim();
    if (!value || busy || value === selectedLocation) return;
    setLive(null);
    setAir(null);
    setForecast(null);
    setSelectedLocation(value);
  }

  useEffect(() => { refresh(selectedLocation); }, [refresh, selectedLocation]);

  const liveObj = live && typeof live === "object" ? live : {};
  const airObj = air && typeof air === "object" ? air : {};
  const providers = liveObj.providers && typeof liveObj.providers === "object" ? liveObj.providers : {};
  const pollutionProvider = providers.openweather_air_pollution || {};
  const weatherProvider = providers.openweather_weather || {};
  const components = pollutionProvider.components || {};
  const current = { ...airObj, ...liveObj, ...(liveObj.current && typeof liveObj.current === "object" ? liveObj.current : {}) };
  const pm25 = numberValue(components.pm2_5 ?? pick(current, ["pm25", "pm2_5", "PM2_5", "PM2.5", "pm2_5_ug_m3"]));
  const pm10 = numberValue(components.pm10 ?? pick(current, ["pm10", "PM10"]));
  const aqi = numberValue(
    airObj.current_aqi?.value ??
    airObj.current_aqi ??
    liveObj.current_aqi?.value ??
    liveObj.india_aqi
);
  const temp = numberValue(weatherProvider.temperature_c ?? pick(current, ["temperature", "temp", "temperature_c", "temp_c"]));
  const humidity = numberValue(weatherProvider.humidity_percent ?? pick(current, ["humidity", "relative_humidity"]));
  const windMs = numberValue(weatherProvider.wind_speed_m_s);
  const wind = numberValue(weatherProvider.wind_speed_kph ?? (windMs !== null ? windMs * 3.6 : null) ?? pick(current, ["wind_speed", "windSpeed", "wind_speed_kmh"]));
  const location = formatLocation(liveObj.location?.resolved_name || liveObj.location?.requested || pick(current, ["city", "station_name", "requested_location"], selectedLocation));
  const rawStations = unwrap(hotspots);
  const stations = rawStations.map((s, i) => ({
    ...s,
    name: formatLocation(pick(s, ["station_name", "name", "station", "location"], `Station ${i + 1}`), `Station ${i + 1}`),
    lat: numberValue(pick(s, ["latitude", "lat", "y"])),
    lon: numberValue(pick(s, ["longitude", "lon", "lng", "x"])),
    pm25: numberValue(pick(s, ["mean_pm25", "pm25", "pm2_5", "avg_pm25", "mean_PM2_5"]))
  })).filter(s => s.lat !== null && s.lon !== null);
  const displayedStations = stations.length ? stations : sampleStations;
  const forecastRows = unwrap(forecast).map((x, i) => ({
    time: pick(x, ["time", "timestamp", "datetime", "date"], `T+${i + 1}`),
    value: numberValue(pick(x, ["pm25", "pm2_5_estimate", "predicted_pm25", "prediction", "predicted", "value", "yhat"]))
  })).filter(x => x.value !== null);
  const singleForecastValue = numberValue(forecast?.predicted_pm25);
  const trend = forecastRows.length
    ? forecastRows
    : singleForecastValue !== null
      ? [{ time: "Next hour", value: singleForecastValue }]
      : [];

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
    const rows = unwrap(data).filter(
      row => row !== null && row !== undefined && typeof row === "object"
    );

    if (!rows.length) {
      return <EmptyState title={emptyMessage || "No records returned"} />;
    }

    return (
      <div className="data-list">
        {rows.map((row, i) => {
          const isAnomaly =
            row.station_name != null ||
            row.timestamp != null ||
            row.pm25 != null ||
            row.anomaly_score != null;

          const rowTitle = isAnomaly
            ? (row.station_name || `Record ${i + 1}`)
            : pick(
                row,
                ["title", "name", "station", "location", "type", "category"],
                `Record ${i + 1}`
              );

          const details = isAnomaly
            ? [
                row.timestamp != null
                  ? `Timestamp: ${new Date(row.timestamp).toLocaleString()}`
                  : null,
                row.pm25 != null
                  ? `PM2.5: ${row.pm25} Âµg/mÂ³`
                  : null,
                row.anomaly_score != null
                  ? `Anomaly score: ${Number(row.anomaly_score).toFixed(4)}`
                  : null
              ].filter(Boolean).join(" | ")
            : (
                pick(
                  row,
                  ["description", "message", "reason", "details", "recommendation", "summary"],
                  null
                ) ?? JSON.stringify(row)
              );

          const titleStr =
            typeof rowTitle === "object"
              ? formatLocation(rowTitle)
              : String(rowTitle ?? `Record ${i + 1}`);

          const descStr =
            typeof details === "object"
              ? JSON.stringify(details)
              : String(details);

          return (
            <div className="data-row" key={row.timestamp || row.id || i}>
              <div className="row-bullet">{i + 1}</div>
              <div className="row-content">
                <strong>{titleStr}</strong>
                <p>{descStr}</p>
              </div>
              <ChevronRight size={17} />
            </div>
          );
        })}
      </div>
    );
  }
  function chartPanel(title, subtitle, rows, dataKey = "value", color = "#69d8c2") {
    return <Card><div className="panel-heading"><div><h3>{title}</h3><p>{subtitle}</p></div><Pill>API / forecast</Pill></div>{rows.length ? <div className="chart-area"><ResponsiveContainer width="100%" height="100%"><AreaChart data={rows}><defs><linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity={.28}/><stop offset="95%" stopColor={color} stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="#263340"/><XAxis dataKey="time" tick={{fill:"#8293a4",fontSize:11}} axisLine={false} tickLine={false}/><YAxis tick={{fill:"#8293a4",fontSize:11}} axisLine={false} tickLine={false}/><Tooltip content={<ChartTooltip/>}/><Area type="monotone" dataKey={dataKey} name="PM2.5" stroke={color} strokeWidth={2.5} fill="url(#forecastFill)" connectNulls/></AreaChart></ResponsiveContainer></div> : <EmptyState/>}</Card>;
  }

  function renderOverview() {
    return <>
      <SectionTitle
        eyebrow="ENVIRONMENTAL INTELLIGENCE"
        title="Overview"
        description="A consolidated view of air quality, forecasts, and pollution intelligence for the selected location."
        action={<button className="button-secondary" onClick={refresh}><RefreshCw size={15}/>Refresh</button>}
      />

      <div className="metrics-grid">
        <Metric label="AQI" value={aqi ?? "—"} unit="AQI" detail="Value returned by configured API" icon={Gauge}/>
        <Metric label="PM2.5" value={pm25 ?? "—"} unit="µg/m³" detail="Fine particulate matter" icon={Wind}/>
        <Metric label="PM10" value={pm10 ?? "—"} unit="µg/m³" detail="Coarse particulate matter" icon={Activity}/>
        <Metric label="Temperature" value={temp ?? "—"} unit={temp !== null ? "°C" : ""} detail="Weather provider reading" icon={CloudSun}/>
      </div>

      <div className="content-grid two-one">
        <Card>
          <div className="panel-heading">
            <div>
              <h3>PM2.5 forecast</h3>
              <p>Forecast values returned by the backend</p>
            </div>
            <Pill tone={forecast ? "green" : "neutral"}>{forecast ? "Response received" : "Awaiting data"}</Pill>
          </div>
          {trend.length ? chartPanel("Forecast trend", "PM2.5 concentration (µg/m³)", trend) : <EmptyState title="Forecast unavailable" detail="No usable forecast values were returned for this location."/>}
          {forecast?.forecast_timestamp && <p className="muted">Forecast time: {String(forecast.forecast_timestamp)}</p>}
          {forecast?.prediction_source && <p className="muted">Source: {String(forecast.prediction_source)}</p>}
          {forecast?.model_generated === false && <p className="muted">This is a provider forecast, not a model-generated prediction.</p>}
        </Card>

        <Card>
          <h3>System status</h3>
          <div className="data-list">
            <div className="data-row">
              <Wifi size={18}/>
              <div className="row-content">
                <strong>Backend connection</strong>
                <p>{apiStatus === "online" ? "At least one API endpoint responded." : apiStatus === "checking" ? "Checking configured endpoints." : "No configured endpoint responded successfully."}</p>
              </div>
            </div>
            <div className="data-row">
              <MapPin size={18}/>
              <div className="row-content">
                <strong>Selected location</strong>
                <p>{String(location)}</p>
              </div>
            </div>
            <div className="data-row">
              <Clock3 size={18}/>
              <div className="row-content">
                <strong>Last refresh</strong>
                <p>{lastUpdated ? new Date(lastUpdated).toLocaleString() : "Not refreshed yet"}</p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <Card>
        <div className="panel-heading">
          <div>
            <h3>Pollution hotspots</h3>
            <p>{stations.length ? "Locations returned by the hotspot API" : "No geolocated hotspot records are available yet."}</p>
          </div>
          <Pill>{stations.length ? "API data" : "Awaiting data"}</Pill>
        </div>
        <HotspotMap stations={displayedStations} onSelect={setSelectedStation}/>
        {selectedStation && <div className="selected-note"><MapPin size={14}/>{selectedStation.name} — PM2.5 {selectedStation.pm25 ?? "N/A"} µg/m³</div>}
      </Card>
    </>;
  }
  function renderPage() {
    if (page === "overview") return renderOverview();
    if (page === "live") return <>
      <SectionTitle eyebrow="REAL-TIME MONITORING" title="Live air quality" description="Current environmental readings from the connected ORIVA services." action={<button className="button-secondary" onClick={refresh}><RefreshCw size={15}/>Refresh</button>}/>
      <div className="metrics-grid"><Metric label="AQI" value={aqi ?? "-"} unit="AQI" detail="Reported index" icon={Gauge}/><Metric label="PM2.5" value={pm25 ?? "-"} unit="Ã‚Âµg/mÃ‚Â³" detail="Fine particles" icon={Wind}/><Metric label="PM10" value={pm10 ?? "-"} unit="Ã‚Âµg/mÃ‚Â³" detail="Coarse particles" icon={Activity}/><Metric label="Wind speed" value={wind ?? "-"} unit={wind !== null ? "km/h" : ""} detail="Reported wind speed" icon={CloudSun}/></div>
      <div className="content-grid two-one"><Card><div className="panel-heading"><div><h3>Current API payload</h3><p>Returned values for inspection</p></div><Pill tone={live || air ? "green" : "neutral"}>{live || air ? "Data received" : "No data"}</Pill></div>{live || air ? <pre className="json-view">{JSON.stringify({live, air}, null, 2)}</pre> : <EmptyState/>}</Card><Card><h3>Data provenance</h3><p className="muted">Values appear only when returned by the API. This page does not fabricate live measurements.</p><div className="data-list"><div className="data-row"><Wifi size={18}/><div className="row-content"><strong>API connection</strong><p>{apiStatus === "online" ? "At least one endpoint responded." : "No configured endpoint has responded."}</p></div></div><div className="data-row"><MapPin size={18}/><div className="row-content"><strong>Requested location</strong><p>{String(location)}</p></div></div></div></Card></div>
    </>;
    if (page === "forecast") return <>
      <SectionTitle eyebrow="PREDICTIVE ANALYTICS" title="Forecast & trends" description="Explore predictions returned by the ORIVA forecasting service." action={<button className="button-secondary" onClick={refresh}><RefreshCw size={15}/>Reload forecast</button>}/>
      {chartPanel("PM2.5 forecast","Prediction values returned by the API",trend)}
      <Card><div className="panel-heading"><div><h3>Forecast response</h3><p>Raw response for transparent model inspection</p></div></div>{forecast ? <pre className="json-view">{JSON.stringify(forecast,null,2)}</pre> : <EmptyState/>}</Card>
    </>;
    if (page === "hotspots") return <>
      <SectionTitle eyebrow="SPATIAL INTELLIGENCE" title="Pollution hotspots" description="Explore available station coordinates and returned hotspot classifications." action={<button className="button-secondary" onClick={refresh}><RefreshCw size={15}/>Refresh</button>}/>
      <Card><div className="panel-heading"><div><h3>Station distribution</h3><p>{stations.length ? `${stations.length} geolocated records from API` : "Sample Pune markers are illustrative only"}</p></div><Pill>{stations.length ? "API data" : "Demo map"}</Pill></div><HotspotMap stations={displayedStations} onSelect={setSelectedStation}/>{selectedStation && <div className="selected-note"><MapPin size={14}/>{selectedStation.name} - PM2.5 {selectedStation.pm25 ?? "N/A"} Ã‚Âµg/mÃ‚Â³</div>}</Card>
      <Card><div className="panel-heading"><div><h3>Hotspot records</h3><p>Backend response, if available</p></div></div>{hotspots ? <pre className="json-view">{JSON.stringify(hotspots,null,2)}</pre> : <EmptyState/>}</Card>
    </>;
    if (page === "anomalies") return <><SectionTitle eyebrow="EARLY WARNING" title="Anomaly detection" description="Review anomaly flags and unusual pollution events returned by the backend."/><Card><div className="panel-heading"><div><h3>Detected anomalies</h3><p>API results</p></div><Pill tone={anomalies ? "green" : "neutral"}>{anomalies ? "Response received" : "Awaiting data"}</Pill></div>{listRows(anomalies,"No anomaly records available")}</Card><Card><h3>Raw anomaly response</h3>{anomalies ? <pre className="json-view">{JSON.stringify(anomalies,null,2)}</pre> : <EmptyState/>}</Card></>;
    if (page === "sources") return <><SectionTitle eyebrow="POLLUTION ATTRIBUTION" title="Source analysis" description="Inspect source attribution and diagnostic results from ORIVA."/><Card><div className="panel-heading"><div><h3>Source analysis results</h3><p>Based on the configured source-analysis API</p></div><FlaskConical size={19} className="accent"/></div>{listRows(sources,"No source analysis results available")}</Card><Card><h3>Raw source response</h3>{sources ? <pre className="json-view">{JSON.stringify(sources,null,2)}</pre> : <EmptyState/>}</Card></>;
    if (page === "recommendations") return <><SectionTitle eyebrow="DECISION SUPPORT" title="AI recommendations" description="Review actions returned by the ORIVA recommendation service."/><Card><div className="panel-heading"><div><h3>Recommended actions</h3><p>Recommendations from the backend response</p></div><Lightbulb size={19} className="accent"/></div>{listRows(recommendations,"No recommendations available")}</Card><Card><h3>Raw recommendations response</h3>{recommendations ? <pre className="json-view">{JSON.stringify(recommendations,null,2)}</pre> : <EmptyState/>}</Card></>;
    return <><SectionTitle eyebrow="CONVERSATIONAL INTELLIGENCE" title="ORIVA assistant" description="Ask questions about air quality, forecasts, pollution sources, and environmental policy."/><Card className="assistant-panel"><div className="assistant-heading"><span className="assistant-avatar"><BrainCircuit size={22}/></span><div><strong>ORIVA Intelligence</strong><p>Connected to your configured chat API</p></div><span className={`connection-dot ${apiStatus === "online" ? "connected" : ""}`}/></div><div className="chat-messages">{chatMessages.map((m,i)=><div key={i} className={`chat-message ${m.role}`}><span className="chat-avatar">{m.role === "assistant" ? <Sparkles size={16}/> : "Y"}</span><div className="chat-bubble">{m.content}</div></div>)}{chatBusy && <div className="chat-message assistant"><span className="chat-avatar"><Sparkles size={16}/></span><div className="chat-bubble"><LoaderCircle className="spin" size={17}/> ThinkingÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦</div></div>}</div><form className="chat-form" onSubmit={sendChat}><input value={chatInput} onChange={e=>setChatInput(e.target.value)} placeholder="Ask ORIVA about air qualityÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦" aria-label="Message ORIVA"/><button type="submit" disabled={chatBusy || !chatInput.trim()}><Send size={17}/>Send</button></form><div className="chat-disclaimer">Answers depend on the configured backend, its data sources, and available model integrations.</div></Card></>;
  }

  const filteredNav = nav.filter(item => item.label.toLowerCase().includes(search.toLowerCase()));
  return <ErrorBoundary>
    <div className="app-shell">
    {sidebarOpen && <button className="sidebar-scrim" onClick={()=>setSidebarOpen(false)} aria-label="Close navigation"/>}
    <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-symbol"><Activity size={23}/></div><div><strong>ORIVA<span> AI</span></strong><small>ENVIRONMENTAL INTELLIGENCE</small></div><button className="mobile-close" onClick={()=>setSidebarOpen(false)}><X size={19}/></button></div>
      <div className="workspace"><div className="workspace-icon"><Wind size={18}/></div><div><strong>Air Intelligence</strong><span>Pollution monitoring</span></div><ChevronRight size={15}/></div>
      <div className="sidebar-search"><Search size={15}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Find a pageÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦"/></div>
      <nav className="navigation">{filteredNav.map((item,i)=><React.Fragment key={item.id}>{item.group && <div className="nav-group">{item.group}</div>}<button onClick={()=>changePage(item.id)} className={`nav-item ${page === item.id ? "active" : ""}`}><item.icon size={18}/><span>{item.label}</span>{item.id === "assistant" && <span className="new-tag">AI</span>}</button></React.Fragment>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><Sparkles size={18}/></div><strong>Environmental insights</strong><p>Turn pollution data into better decisions.</p><button onClick={()=>changePage("assistant")}>Ask ORIVA <ArrowUpRight size={14}/></button></div><div className="sidebar-footer"><span className={`status-light ${apiStatus === "online" ? "" : "offline"}`}/><span>{apiStatus === "online" ? "API connected" : "API not connected"}</span><span className="version">v1.0</span></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="topbar-left"><button className="mobile-menu" onClick={()=>setSidebarOpen(true)}><Menu size={21}/></button><div className="breadcrumbs"><span>ORIVA</span><ChevronRight size={14}/><strong>{heading}</strong></div></div><div className="topbar-right"><form className="location-search" onSubmit={submitLocation}>
          <MapPin size={15}/>
          <input aria-label="Search location" value={locationInput}
            onChange={e => setLocationInput(e.target.value)}
            placeholder="Enter city or areaÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦"/>
          <button type="submit" disabled={busy || !locationInput.trim()}>
            {busy ? <LoaderCircle size={14} className="spin"/> : <Search size={14}/>}
            <span>Find</span>
          </button>
        </form><div className={`api-chip ${apiStatus}`}><span className="status-light"/>{apiStatus === "online" ? "API online" : apiStatus === "checking" ? "Checking API" : "API offline"}</div><button className="icon-button" onClick={refresh} title="Refresh data"><RefreshCw size={17} className={busy ? "spin" : ""}/></button><button className="icon-button" onClick={()=>setNotice(notice ? "" : "ORIVA dashboard notifications: API connectivity and data availability are shown in the system status panel.")} title="Notifications"><Bell size={17}/></button></div></header>
      {notice && <div className="notice-bar">{notice}<button onClick={()=>setNotice("")}><X size={15}/></button></div>}
      <div className="page-content">{renderPage()}<footer className="app-footer"><span>ORIVA AI Ãƒâ€šÃ‚Â· Environmental Intelligence</span><span>Data displayed only when returned by configured services</span></footer></div>
    </main>
  </div>
  </ErrorBoundary>;
}







