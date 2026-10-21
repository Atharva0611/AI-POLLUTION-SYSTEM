import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const DEFAULT_LOCATION = "Wagholi, Pune, Maharashtra, India";
const REFRESH_MS = Math.max(60, Number(import.meta.env.VITE_LIVE_REFRESH_SECONDS || 300)) * 1000;
const POLLUTANTS = [
  ["pm2_5", "PM2.5", "µg/m³"], ["pm10", "PM10", "µg/m³"],
  ["no2", "NO₂", "µg/m³"], ["so2", "SO₂", "µg/m³"],
  ["o3", "O₃", "µg/m³"], ["co", "CO", "µg/m³"],
  ["no", "NO", "µg/m³"], ["nh3", "NH₃", "µg/m³"]
];

function fmt(value, digits = 1) {
  return value == null || !Number.isFinite(Number(value)) ? "—" : Number(value).toFixed(digits);
}
function fmtTime(value) {
  if (!value) return "Timestamp unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Invalid timestamp" : date.toLocaleString();
}
function Freshness({ value }) {
  const state = value?.freshness || "unknown";
  const labels = { fresh: "Current", stale: "Stale", delayed: "Delayed", missing_timestamp: "Time missing", invalid_timestamp: "Invalid time", future_timestamp: "Future time" };
  return <span className={`live-freshness live-freshness--${state}`}>{labels[state] || "Unavailable"}</span>;
}
function ProviderStatus({ item, label }) {
  const status = item?.status || "unavailable";
  const ok = status === "ok";
  return <span className={`live-provider-status ${ok ? "is-ok" : "is-warn"}`}><i />{label}: {ok ? "current data verified" : status.replaceAll("_", " ")}</span>;
}
function MapViewport({ center, stations }) {
  const map = useMap();
  useEffect(() => {
    const points = stations.filter(s => Number.isFinite(Number(s.latitude)) && Number.isFinite(Number(s.longitude)))
      .map(s => [Number(s.latitude), Number(s.longitude)]);
    if (points.length > 1) map.fitBounds(points, { padding: [28, 28], maxZoom: 12 });
    else if (center?.latitude != null && center?.longitude != null) map.setView([center.latitude, center.longitude], 11);
  }, [map, center?.latitude, center?.longitude, stations]);
  return null;
}
function MetricCard({ label, value, unit, sub, state = "normal" }) {
  return <article className={`live-metric live-metric--${state}`}><span>{label}</span><strong>{value ?? "—"}{value != null && value !== "—" && unit ? <small> {unit}</small> : null}</strong><p>{sub || "No eligible current observation"}</p></article>;
}

export default function LiveAirQuality() {
  const [draft, setDraft] = useState(DEFAULT_LOCATION);
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastRefresh, setLastRefresh] = useState(null);
  const [stationSearch, setStationSearch] = useState("");
  const [selectedStationId, setSelectedStationId] = useState(null);
  const requestId = useRef(0);

  const refresh = useCallback(async (target = location) => {
    const request = ++requestId.current;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/live/air-quality?location=${encodeURIComponent(target)}`, { headers: { Accept: "application/json" } });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || `Live data API returned HTTP ${response.status}`);
      if (request !== requestId.current) return;
      setData(body);
      setLastRefresh(new Date().toISOString());
      if (body.status === "unavailable") setError("No provider returned eligible current data. Check the source-specific status below; historical readings are intentionally not substituted.");
    } catch (err) {
      if (request === requestId.current) setError(err.message || "Could not fetch current environmental data.");
    } finally {
      if (request === requestId.current) setLoading(false);
    }
  }, [location]);

  const searchLocation = event => {
    event.preventDefault();
    const target = draft.trim();
    if (!target) { setError("Enter a town, city, or locality."); return; }
    setLocation(target);
  };

  useEffect(() => {
    refresh(location);
    const timer = setInterval(() => refresh(location), REFRESH_MS);
    return () => { clearInterval(timer); requestId.current += 1; };
  }, [location, refresh]);

  const providers = data?.providers || {};
  const aq = providers.openweather_air_pollution || {};
  const weather = providers.openweather_weather || {};
  const openaq = providers.openaq || {};
  const components = aq.components || {};
  const liveMeasurements = openaq.live_measurements || [];
  const stations = openaq.stations || [];
  const filteredStations = useMemo(() => {
    const term = stationSearch.trim().toLowerCase();
    return stations.filter(s => !term || `${s.name || ""} ${s.locality || ""} ${s.id || ""}`.toLowerCase().includes(term));
  }, [stations, stationSearch]);
  const selectedStation = stations.find(s => String(s.id) === String(selectedStationId)) || null;
  const center = data?.location || {};
  const currentCount = liveMeasurements.length + (aq.status === "ok" ? 1 : 0) + (weather.status === "ok" ? 1 : 0);

  return <main className="aq-page live-environment-page">
    <style>{`
      .live-environment-page{gap:18px}.live-hero{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;flex-wrap:wrap}
      .live-hero h1{font-size:clamp(26px,3.2vw,38px);letter-spacing:-.04em;margin:7px 0 8px;color:#18352e}
      .live-hero p{max-width:720px}.live-search{display:flex;gap:8px;min-width:min(100%,440px);flex:0 1 480px}
      .live-search input{min-width:0;flex:1;border:1px solid #d6e1e3;border-radius:7px;padding:11px 12px;background:#fff;color:#203640}
      .live-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:13px 15px;background:#fff;border:1px solid #dce4e8;border-radius:8px}
      .live-location{display:grid;gap:4px}.live-location strong{font-size:15px;color:#203c34}.live-location small{font-size:11px;color:#71828a}
      .live-statuses{display:flex;gap:8px;flex-wrap:wrap}.live-provider-status{display:inline-flex;align-items:center;gap:6px;font-size:10px;font-weight:700;border:1px solid #dce4e8;border-radius:5px;padding:6px 8px;color:#687981;background:#f8fafb;text-transform:capitalize}
      .live-provider-status i{width:6px;height:6px;border-radius:50%;background:#aab7bc}.live-provider-status.is-ok{color:#176b53;background:#edf6f1;border-color:#d0e6d9}.live-provider-status.is-ok i{background:#16865f}.live-provider-status.is-warn{color:#8a5b13;background:#fff7e8;border-color:#f0e1bf}
      .live-metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}.live-metric{min-width:0;background:#fff;border:1px solid #dce4e8;border-radius:8px;padding:15px;display:grid;gap:9px;align-content:start}.live-metric>span{font-size:11px;color:#627780;font-weight:650}.live-metric>strong{font-size:clamp(20px,2.2vw,29px);letter-spacing:-.035em;color:#203b33;overflow-wrap:anywhere}.live-metric>strong small{font-size:11px;font-weight:600;letter-spacing:0;color:#6d8087}.live-metric p{font-size:10px;line-height:1.5;color:#71828a;margin:0}.live-metric--accent{border-top:3px solid #17765d}.live-section-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:14px}.live-section-heading h2{font-size:17px;color:#203640;margin:0 0 5px}.live-section-heading p{font-size:11px;color:#71828a;margin:0;line-height:1.6}.live-grid-two{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:16px}.live-panel{min-width:0;background:#fff;border:1px solid #dce4e8;border-radius:8px;padding:17px}.live-pollutants{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.live-pollutant{padding:12px;border:1px solid #e3e9eb;border-radius:6px;background:#fbfcfc;min-width:0}.live-pollutant span,.live-pollutant strong,.live-pollutant small{display:block}.live-pollutant span{font-size:10px;color:#71828a}.live-pollutant strong{font-size:18px;color:#243f36;margin:7px 0 4px;overflow-wrap:anywhere}.live-pollutant small{font-size:9px;color:#829198}.live-map{height:330px;width:100%;border-radius:6px;z-index:0}.live-station-list{display:grid;gap:6px;max-height:280px;overflow:auto;margin-top:10px}.live-station{width:100%;display:flex;align-items:center;gap:10px;text-align:left;padding:10px;border:1px solid #e3e9eb;border-radius:6px;background:#fff;color:#203640}.live-station.selected{background:#edf6f1;border-color:#cce2d7}.live-station strong,.live-station small{display:block}.live-station strong{font-size:11px}.live-station small{font-size:10px;color:#71828a;margin-top:4px}.live-station .station-id{margin-left:auto;font:10px ui-monospace,monospace;color:#6c7f87}.live-measurement-table{width:100%;border-collapse:collapse;font-size:11px;text-align:left}.live-measurement-table th,.live-measurement-table td{padding:10px 8px;border-bottom:1px solid #e7edef;vertical-align:top}.live-measurement-table th{font-size:10px;color:#657781;background:#f7f9fa}.live-measurement-table td{color:#314953}.live-measurement-table td small{display:block;color:#75858c;font-size:9px;margin-top:4px}.live-freshness{display:inline-block;padding:4px 6px;border-radius:4px;background:#eef1f3;color:#586b74;font-size:9px;font-weight:750;white-space:nowrap}.live-freshness--fresh{background:#e9f5ee;color:#176b53}.live-freshness--stale,.live-freshness--invalid_timestamp,.live-freshness--missing_timestamp,.live-freshness--future_timestamp{background:#fdeeed;color:#a13731}.live-alert{padding:12px 14px;border:1px solid #f1cfcb;background:#fff0ef;color:#96352d;border-radius:6px;font-size:12px;line-height:1.6}.live-empty{padding:18px 8px;color:#71828a;font-size:12px;line-height:1.6}.live-provenance{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.live-source-card{padding:13px;border:1px solid #e0e7ea;border-radius:6px;background:#fafcfc;min-width:0}.live-source-card strong{display:block;font-size:11px;color:#203640;margin-bottom:7px}.live-source-card p{font-size:10px;line-height:1.65;color:#687c85;margin:0;overflow-wrap:anywhere}.live-loading{color:#647680;font-size:12px;padding:12px 0}@media(max-width:1100px){.live-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.live-grid-two{grid-template-columns:1fr}}@media(max-width:650px){.live-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.live-pollutants{grid-template-columns:repeat(2,minmax(0,1fr))}.live-provenance{grid-template-columns:1fr}.live-search{min-width:100%}.live-map{height:270px}.live-panel{padding:12px}.live-measurement-table{min-width:590px}.live-table-wrap{overflow:auto}}
    `}</style>

    <header className="live-hero">
      <div><div className="aq-eyebrow">ORIVA / CURRENT ENVIRONMENT</div><h1>Live air quality &amp; weather</h1><p>Current provider observations with timestamp validation, source attribution, and location-aware monitoring. Historical analytics and model forecasts remain separate.</p></div>
      <form className="live-search" onSubmit={searchLocation}><input aria-label="Search location" value={draft} onChange={e => setDraft(e.target.value)} placeholder="Search town, city, or locality" /><button className="aq-button" disabled={loading || !draft.trim()}>{loading ? "Checking…" : "Search location"}</button></form>
    </header>

    <section className="live-toolbar">
      <div className="live-location"><strong>{center.resolved_name || location}</strong><small>{center.latitude != null ? `Coordinates: ${Number(center.latitude).toFixed(5)}, ${Number(center.longitude).toFixed(5)}` : "Location coordinates not resolved"} · Last dashboard fetch: {fmtTime(lastRefresh)}</small></div>
      <div className="live-statuses"><ProviderStatus item={openaq} label="OpenAQ" /><ProviderStatus item={aq} label="OpenWeather air" /><ProviderStatus item={weather} label="OpenWeather weather" /><button className="aq-button aq-button-secondary" onClick={() => refresh(location)} disabled={loading}>{loading ? "Refreshing…" : "↻ Refresh now"}</button></div>
    </section>

    {error && <div className="live-alert" role="alert">{error}</div>}
    {loading && !data && <div className="live-loading" role="status">Resolving location and requesting current provider data…</div>}

    <section>
      <div className="live-section-heading"><div><h2>Current conditions</h2><p>Only timestamp-validated values appear as current. A dash means no eligible value was returned.</p></div><span className="aq-count">{currentCount} current source records</span></div>
      <div className="live-metrics">
        <MetricCard label="OpenWeather AQI" value={aq.status === "ok" && aq.aqi != null ? aq.aqi : "—"} unit={aq.status === "ok" && aq.aqi != null ? "/ 5" : ""} state="accent" sub={aq.status === "ok" ? `OpenWeather scale · observed ${fmtTime(aq.observed_at)}` : aq.error || "No current AQI"} />
        <MetricCard label="PM2.5" value={aq.status === "ok" ? fmt(components.pm2_5) : "—"} unit={aq.status === "ok" && components.pm2_5 != null ? "µg/m³" : ""} sub="OpenWeather · provider value" />
        <MetricCard label="PM10" value={aq.status === "ok" ? fmt(components.pm10) : "—"} unit={aq.status === "ok" && components.pm10 != null ? "µg/m³" : ""} sub="OpenWeather · provider value" />
        <MetricCard label="Temperature" value={weather.status === "ok" ? fmt(weather.temperature_c) : "—"} unit={weather.status === "ok" && weather.temperature_c != null ? "°C" : ""} sub={weather.status === "ok" ? `Observed ${fmtTime(weather.observed_at)}` : weather.error || "Weather unavailable"} />
        <MetricCard label="Humidity" value={weather.status === "ok" ? fmt(weather.humidity_percent, 0) : "—"} unit={weather.status === "ok" && weather.humidity_percent != null ? "%" : ""} sub="OpenWeather current weather" />
        <MetricCard label="Wind speed" value={weather.status === "ok" ? fmt(weather.wind_speed_m_s) : "—"} unit={weather.status === "ok" && weather.wind_speed_m_s != null ? "m/s" : ""} sub="OpenWeather current weather" />
      </div>
    </section>

    <section className="live-panel">
      <div className="live-section-heading"><div><h2>OpenWeather pollutant detail</h2><p>Provider-reported concentrations. AQI uses OpenWeather's 1–5 index, not the CPCB 0–500 scale.</p></div><Freshness value={aq} /></div>
      {aq.status === "ok" ? <><div className="live-pollutants">{POLLUTANTS.map(([key, label, unit]) => <div className="live-pollutant" key={key}><span>{label}</span><strong>{fmt(components[key], 2)}</strong><small>{components[key] == null ? "Not supplied" : unit}</small></div>)}</div><p className="aq-footnote">Observed: {fmtTime(aq.observed_at)} · Age: {aq.age_minutes == null ? "unknown" : `${aq.age_minutes} minutes`} · Source: OpenWeather current Air Pollution API.</p></> : <div className="live-empty">{aq.error || "No timestamp-validated OpenWeather pollution observation is available. No historical value was substituted."}</div>}
    </section>

    <div className="live-grid-two">
      <section className="live-panel">
        <div className="live-section-heading"><div><h2>OpenAQ sensor network</h2><p>{stations.length} nearby station records · {liveMeasurements.length} measurements meet the configured live-age limit.</p></div><span className="aq-count">{liveMeasurements.length} live</span></div>
        <input className="aq-search" aria-label="Filter OpenAQ stations" placeholder="Filter station name or ID…" value={stationSearch} onChange={e => setStationSearch(e.target.value)} />
        {stations.length ? <div className="live-station-list">{filteredStations.map(s => <button key={s.id} className={`live-station ${String(selectedStationId) === String(s.id) ? "selected" : ""}`} onClick={() => setSelectedStationId(s.id)}><span aria-hidden="true">●</span><span><strong>{s.name || "Unnamed station"}</strong><small>{s.locality || "Locality not provided"} · {s.latitude != null && s.longitude != null ? `${Number(s.latitude).toFixed(4)}, ${Number(s.longitude).toFixed(4)}` : "Coordinates unavailable"}</small></span><span className="station-id">#{s.id}</span></button>)}</div> : <div className="live-empty">{openaq.error || "No OpenAQ stations returned for this location. No station has been invented."}</div>}
        <p className="aq-footnote">Station presence does not mean its measurements are current. Stale values are excluded from the live summary.</p>
      </section>
      <section className="live-panel">
        <div className="live-section-heading"><div><h2>Station map</h2><p>OpenAQ station coordinates for the selected location.</p></div><span className="aq-count">{stations.filter(s => s.latitude != null && s.longitude != null).length} mapped</span></div>
        {center.latitude != null && center.longitude != null ? <MapContainer className="live-map" center={[Number(center.latitude), Number(center.longitude)]} zoom={11} scrollWheelZoom><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><MapViewport center={center} stations={stations} />{stations.filter(s => s.latitude != null && s.longitude != null).map(s => <CircleMarker key={s.id} center={[Number(s.latitude), Number(s.longitude)]} radius={String(selectedStationId) === String(s.id) ? 10 : 7} pathOptions={{ color: String(selectedStationId) === String(s.id) ? "#176b53" : "#4f9d80", fillColor: "#4f9d80", fillOpacity: .8 }}><Popup><strong>{s.name || "OpenAQ station"}</strong><br />ID {s.id}<br />{s.locality || "Locality not supplied"}</Popup></CircleMarker>)}</MapContainer> : <div className="live-empty">Map unavailable until the location is resolved.</div>}
      </section>
    </div>

    <section className="live-panel">
      <div className="live-section-heading"><div><h2>{selectedStation ? selectedStation.name || `Station ${selectedStation.id}` : "Eligible OpenAQ measurements"}</h2><p>Only observations meeting the strict live-data threshold are listed here. Values retain their source units and timestamps.</p></div><span className="aq-count">OpenAQ v3</span></div>
      <div className="live-table-wrap"><table className="live-measurement-table"><thead><tr><th>Station</th><th>Pollutant</th><th>Value</th><th>Observation time</th><th>Age</th><th>Freshness</th></tr></thead><tbody>{liveMeasurements.filter(m => !selectedStation || String(m.station_id) === String(selectedStation.id)).map((m, i) => <tr key={`${m.station_id}-${m.sensor_id}-${i}`}><td>{m.station || `Station ${m.station_id}`}<small>ID {m.station_id}</small></td><td><strong>{String(m.pollutant || "").toUpperCase()}</strong></td><td>{m.value == null ? "—" : fmt(m.value, 2)} {m.unit || ""}</td><td>{fmtTime(m.observed_at_utc)}</td><td>{m.age_minutes == null ? "Unknown" : `${m.age_minutes} min`}</td><td><Freshness value={m} /></td></tr>)}</tbody></table></div>
      {!liveMeasurements.length && <div className="live-empty">{openaq.error || "No eligible OpenAQ measurements. Historical or stale readings will not be used as a fallback."}</div>}
    </section>

    <section className="live-panel">
      <div className="live-section-heading"><div><h2>Weather &amp; data provenance</h2><p>Source status and timestamps are shown independently; provider values are never averaged into a synthetic AQI.</p></div></div>
      <div className="live-pollutants">
        {[{name:"OpenAQ sensors",item:openaq,time:openaq.retrieved_at,desc:`${liveMeasurements.length} eligible measurements; ${stations.length} stations`},{name:"OpenWeather pollution",item:aq,time:aq.observed_at,desc:`AQI scale: ${aq.aqi_scale || "OpenWeather 1–5"}`},{name:"OpenWeather weather",item:weather,time:weather.observed_at,desc:`${weather.condition || "Current weather"} · pressure ${weather.pressure_hpa ?? "—"} hPa`}].map(source => <article className="live-source-card" key={source.name}><strong>{source.name}</strong><p>Status: {source.item.status || "unavailable"}<br />Observation: {fmtTime(source.time)}<br />{source.desc}<br />{source.item.error || "No provider error reported."}</p></article>)}
      </div>
      <p className="aq-footnote">Dashboard fetch: {fmtTime(lastRefresh)} · Automatic refresh: every {Math.round(REFRESH_MS / 60000)} minutes · Provider timestamps are converted to your browser's local time. “Current” means the provider timestamp passes the configured age threshold, not that the sensor updates continuously.</p>
    </section>
    <footer className="aq-page-footer">Live observations: OpenAQ and OpenWeather. Historical DBSCAN hotspots and XGBoost/SHAP predictions are available in their separate navigation sections and are never used to fill current cards.</footer>
  </main>;
}
