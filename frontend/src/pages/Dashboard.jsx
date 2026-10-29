import { useCallback, useEffect, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8003").replace(/\/$/, "");
const DEFAULT_LOCATION = "Wagholi, Pune, Maharashtra, India";
const number = (v, d = 1) => v == null || !Number.isFinite(Number(v)) ? "â€”" : Number(v).toFixed(d);
const localTime = v => { if (!v) return "Timestamp unavailable"; const d = new Date(v); return Number.isNaN(d.getTime()) ? "Invalid timestamp" : d.toLocaleString(); };

function Status({ value, label }) {
  const ok = value?.status === "ok";
  return <span className={`overview-status ${ok ? "ok" : "warn"}`}><i />{label}: {ok ? "current" : (value?.status || "unavailable").replaceAll("_", " ")}</span>;
}
function Card({ label, value, unit, source, timestamp }) {
  return <article className="oriva-dash-metric"><span>{label}</span><strong>{value ?? "â€”"}{value != null && value !== "â€”" && unit ? ` ${unit}` : ""}</strong><small>{source || "No current observation"}{timestamp ? ` Â· ${localTime(timestamp)}` : ""}</small></article>;
}

export default function Dashboard() {
  const [locationInput, setLocationInput] = useState(DEFAULT_LOCATION);
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);

  const refresh = useCallback(async (target = location) => {
    setLoading(true); setError("");
    try {
      const response = await fetch(`${API_BASE}/api/live/air-quality?location=${encodeURIComponent(target)}`);
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || `Live data API returned HTTP ${response.status}`);
      setData(body); setLastRefresh(new Date().toISOString());
      if (body.status !== "ok") setError("No provider returned timestamp-validated current data. Historical records are not used as a fallback.");
    } catch (e) { setError(e.message || "Live data is unavailable."); }
    finally { setLoading(false); }
  }, [location]);

  useEffect(() => { refresh(location); }, [location, refresh]);
  const submit = e => { e.preventDefault(); const q = locationInput.trim(); if (q) setLocation(q); };
  const p = data?.providers || {};
  const air = p.openweather_air_pollution || {};
  const weather = p.openweather_weather || {};
  const openaq = p.openaq || {};
  const c = air.components || {};
  const fresh = openaq.live_measurements || [];
  const stations = openaq.stations || [];

  return <main className="oriva-dashboard">
    <style>{`
      .overview-hero{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap}.overview-hero h1{font-size:clamp(25px,3vw,35px);margin:7px 0;color:#203640;letter-spacing:-.035em}.overview-hero p{font-size:12px;color:#647680;max-width:700px;line-height:1.7}.overview-search{display:flex;gap:8px;min-width:min(100%,430px)}.overview-search input{flex:1;min-width:0;border:1px solid #d7e1e5;border-radius:6px;padding:10px 12px;background:#fff;color:#203640}.overview-panel{background:#fff;border:1px solid #dce4e8;border-radius:8px;padding:17px;min-width:0}.overview-panel h2{font-size:16px;color:#203640;margin:0 0 6px}.overview-panel p{font-size:11px;color:#647680;line-height:1.6}.overview-status{display:inline-flex;align-items:center;gap:6px;border:1px solid #dce4e8;border-radius:5px;padding:6px 8px;font-size:10px;text-transform:capitalize;color:#687981;background:#f8fafb}.overview-status i{width:6px;height:6px;border-radius:50%;background:#aab7bc}.overview-status.ok{color:#176b53;background:#edf6f1;border-color:#d0e6d9}.overview-status.ok i{background:#16865f}.overview-status.warn{color:#8a5b13;background:#fff7e8;border-color:#f0e1bf}.overview-statuses{display:flex;gap:7px;flex-wrap:wrap}.overview-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:11px}.overview-lower{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.overview-small-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.overview-small-card{background:#fafcfc;border:1px solid #e2e9eb;border-radius:6px;padding:11px;min-width:0}.overview-small-card span,.overview-small-card strong,.overview-small-card small{display:block}.overview-small-card span{font-size:10px;color:#71828a}.overview-small-card strong{font-size:17px;color:#203640;margin:7px 0;overflow-wrap:anywhere}.overview-small-card small{font-size:9px;color:#71828a}.overview-alert{padding:12px 14px;border:1px solid #f1cfcb;background:#fff0ef;color:#96352d;border-radius:6px;font-size:12px;line-height:1.6}.overview-meta{font-size:10px;color:#71828a;line-height:1.7}.overview-links{display:flex;gap:8px;flex-wrap:wrap}.overview-links span{font-size:10px;border:1px solid #dce4e8;border-radius:5px;padding:7px 9px;color:#536a73;background:#f8fafb}@media(max-width:1100px){.overview-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:650px){.overview-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.overview-lower{grid-template-columns:1fr}.overview-small-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.overview-search{min-width:100%}}
    `}</style>
    <header className="overview-hero"><div><div className="oriva-dash-eyebrow">ENVIRONMENTAL INTELLIGENCE / OVERVIEW</div><h1>Current conditions</h1><p>Live provider data for your selected location. Forecasts, SHAP explanations, and DBSCAN hotspot analysis are separate model or historical modules.</p></div><form className="overview-search" onSubmit={submit}><input aria-label="Overview location" value={locationInput} onChange={e => setLocationInput(e.target.value)} placeholder="Search a town or city"/><button className="oriva-dash-btn" disabled={loading || !locationInput.trim()}>{loading ? "Loadingâ€¦" : "Update location"}</button></form></header>
    <section className="overview-panel"><div className="overview-statuses"><Status value={openaq} label="OpenAQ"/><Status value={air} label="OpenWeather air"/><Status value={weather} label="OpenWeather weather"/></div><h2 style={{marginTop:13}}>{data?.location?.resolved_name || location}</h2><p>{data?.location?.latitude != null ? `Coordinates: ${Number(data.location.latitude).toFixed(5)}, ${Number(data.location.longitude).toFixed(5)}` : "Location coordinates unavailable"} Â· Last fetch: {localTime(lastRefresh)}</p></section>
    {error && <div className="overview-alert" role="alert">{error}</div>}
    <section><div className="overview-panel" style={{marginBottom:12}}><h2>Current air quality &amp; weather</h2><p>OpenWeather AQI is its own 1â€“5 index. It is not CPCB AQI. Values appear only when the provider observation timestamp passes the configured live-data threshold.</p></div><div className="overview-grid">
      <Card label="OpenWeather AQI" value={air.status === "ok" && air.aqi != null ? air.aqi : "â€”"} unit={air.status === "ok" && air.aqi != null ? "/ 5" : ""} source="OpenWeather 1â€“5 scale" timestamp={air.observed_at}/>
      <Card label="PM2.5" value={air.status === "ok" ? number(c.pm2_5) : "â€”"} unit={air.status === "ok" && c.pm2_5 != null ? "Âµg/mÂ³" : ""} source="OpenWeather"/>
      <Card label="PM10" value={air.status === "ok" ? number(c.pm10) : "â€”"} unit={air.status === "ok" && c.pm10 != null ? "Âµg/mÂ³" : ""} source="OpenWeather"/>
      <Card label="Temperature" value={weather.status === "ok" ? number(weather.temperature_c) : "â€”"} unit={weather.status === "ok" && weather.temperature_c != null ? "Â°C" : ""} source="OpenWeather weather" timestamp={weather.observed_at}/>
      <Card label="Humidity" value={weather.status === "ok" ? number(weather.humidity_percent, 0) : "â€”"} unit={weather.status === "ok" && weather.humidity_percent != null ? "%" : ""} source="OpenWeather weather"/>
      <Card label="Wind speed" value={weather.status === "ok" ? number(weather.wind_speed_m_s) : "â€”"} unit={weather.status === "ok" && weather.wind_speed_m_s != null ? "m/s" : ""} source="OpenWeather weather"/>
    </div></section>
    <div className="overview-lower">
      <section className="overview-panel"><h2>OpenAQ sensor observations</h2><p>{stations.length} nearby stations Â· {fresh.length} measurements meet the live threshold.</p><div className="overview-small-grid"><div className="overview-small-card"><span>Stations</span><strong>{stations.length}</strong><small>Returned by OpenAQ</small></div><div className="overview-small-card"><span>Eligible readings</span><strong>{fresh.length}</strong><small>Age-validated</small></div><div className="overview-small-card"><span>Live data window</span><strong>180 min</strong><small>Configurable in backend</small></div></div><p className="overview-meta">{openaq.error || "OpenAQ observations are third-party sensor reports, not automatically official CPCB AQI."}</p></section>
      <section className="overview-panel"><h2>Model intelligence</h2><p>These modules are deliberately separate from current provider readings.</p><div className="overview-links"><span>XGBoost PM2.5 forecasting</span><span>SHAP feature attribution</span><span>Historical DBSCAN clusters</span><span>Interactive hotspot map</span></div><p className="overview-meta">Use the Forecast &amp; SHAP page for model predictions and feature explanations, and Hotspot Map for historical spatial clustering. Neither is a fallback for missing live AQI.</p></section>
    </div>
    <footer className="oriva-dash-muted">Automatic refresh is available on the Live Air Quality page. Current fetch: {localTime(data?.updated_at)}. A missing value is shown as unavailable, never as zero.</footer>
  </main>;
}
