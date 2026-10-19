import { useCallback, useEffect, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");

const endpoints = [
  { key: "pollution", label: "Current pollution", path: "/api/pollution/current" },
  { key: "snapshot", label: "Current snapshot", path: "/api/current-snapshot/" },
  { key: "forecast", label: "Forecast stations", path: "/api/forecast/stations" }
];

function findValue(value, candidates, depth = 0) {
  if (!value || typeof value !== "object" || depth > 4) return undefined;
  for (const key of candidates) {
    if (value[key] !== undefined && value[key] !== null &&
        typeof value[key] !== "object") return value[key];
  }
  for (const child of Object.values(value)) {
    if (child && typeof child === "object") {
      const result = findValue(child, candidates, depth + 1);
      if (result !== undefined) return result;
    }
  }
  return undefined;
}

function Metric({ label, value, unit, accent }) {
  return (
    <article className="oriva-dash-metric" style={{ "--metric-accent": accent }}>
      <span>{label}</span>
      <strong>{value ?? "—"}{value != null && unit ? ` ${unit}` : ""}</strong>
      <small>{value == null ? "Not provided by API" : "Returned by backend"}</small>
    </article>
  );
}

export default function Dashboard() {
  const [data, setData] = useState({});
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [updated, setUpdated] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    const nextData = {};
    const nextErrors = {};

    await Promise.all(endpoints.map(async endpoint => {
      try {
        const response = await fetch(`${API_BASE}${endpoint.path}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        nextData[endpoint.key] = await response.json();
      } catch (error) {
        nextErrors[endpoint.key] = error.message || "Request failed";
      }
    }));

    setData(nextData);
    setErrors(nextErrors);
    setUpdated(new Date().toLocaleTimeString());
    setLoading(false);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const combined = { ...data.snapshot, ...data.pollution };
  const aqi = findValue(combined, ["aqi", "AQI", "air_quality_index", "overall_aqi"]);
  const pm25 = findValue(combined, ["pm25", "PM2.5", "pm2_5", "pm25_mean"]);
  const pm10 = findValue(combined, ["pm10", "PM10", "pm10_mean"]);
  const temperature = findValue(combined, ["temperature", "temp_c", "temperature_c"]);
  const station = findValue(combined, ["station_name", "station", "resolved_station", "location"]);
  const forecastRows = Array.isArray(data.forecast)
    ? data.forecast
    : Object.values(data.forecast || {}).find(Array.isArray) || [];

  return (
    <main className="oriva-dashboard">
      <style>{`
        .oriva-dashboard{padding:clamp(16px,3vw,30px);color:var(--text,#e8eef7);display:grid;gap:22px;align-content:start;animation:oriva-dash-in .35s ease-out}
        @keyframes oriva-dash-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
        .oriva-dash-heading{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
        .oriva-dash-heading h1{font-size:clamp(25px,3vw,36px);margin:6px 0}
        .oriva-dash-eyebrow{color:#54d6b0;font-size:11px;font-weight:800;letter-spacing:.15em}
        .oriva-dash-muted{color:var(--muted,#9aa9bd);font-size:13px}
        .oriva-dash-btn{border:0;border-radius:10px;padding:11px 16px;background:#54d6b0;color:#06251e;font-weight:800;cursor:pointer}
        .oriva-dash-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:13px}
        .oriva-dash-metric{padding:18px;border-radius:15px;border:1px solid var(--border,#273448);background:var(--panel,#101a29);display:grid;gap:13px;min-width:0;transition:transform .2s,border-color .2s}
        .oriva-dash-metric:hover{transform:translateY(-3px);border-color:var(--metric-accent,#54d6b0)}
        .oriva-dash-metric span{font-size:12px;color:var(--muted,#9aa9bd)}
        .oriva-dash-metric strong{font-size:clamp(22px,2vw,30px);overflow-wrap:anywhere}
        .oriva-dash-metric small{font-size:11px;color:var(--muted,#9aa9bd)}
        .oriva-dash-panel{padding:18px;border:1px solid var(--border,#273448);border-radius:15px;background:var(--panel,#101a29);min-width:0}
        .oriva-dash-panel h2{font-size:17px;margin:0 0 12px}
        .oriva-dash-status{padding:12px;border-radius:10px;background:rgba(84,214,176,.08);border:1px solid rgba(84,214,176,.22);font-size:13px}
        .oriva-dash-error{padding:12px;border-radius:10px;background:rgba(220,38,38,.1);color:#fecaca;font-size:13px}
        .oriva-dash-table-wrap{overflow:auto}
        .oriva-dash-table{width:100%;border-collapse:collapse;font-size:13px;text-align:left}
        .oriva-dash-table th,.oriva-dash-table td{padding:11px;border-bottom:1px solid var(--border,#273448);white-space:nowrap}
        .oriva-dash-table th{color:var(--muted,#9aa9bd)}
        .oriva-dash-json{max-height:250px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:var(--muted,#9aa9bd)}
        @media(prefers-reduced-motion:reduce){.oriva-dashboard,.oriva-dash-metric{animation:none;transition:none}}
      `}</style>

      <header className="oriva-dash-heading">
        <div>
          <div className="oriva-dash-eyebrow">ORIVA / ENVIRONMENTAL INTELLIGENCE</div>
          <h1>Overview Dashboard</h1>
          <p className="oriva-dash-muted">
            Pollution and forecast information returned by your connected backend.
          </p>
        </div>
        <button className="oriva-dash-btn" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing…" : "↻ Refresh data"}
        </button>
      </header>

      <div className="oriva-dash-status">
        {loading ? "Connecting to ORIVA data services…" :
          Object.keys(errors).length === 0
            ? `Data requests completed · Last checked ${updated}`
            : `Some data sources are unavailable · Last checked ${updated}`}
      </div>

      {Object.entries(errors).map(([key, message]) => (
        <div className="oriva-dash-error" role="alert" key={key}>
          {endpoints.find(e => e.key === key)?.label}: {message}
        </div>
      ))}

      <section className="oriva-dash-grid">
        <Metric label="Air Quality Index" value={aqi} accent="#f59e0b" />
        <Metric label="PM2.5" value={pm25} unit="µg/m³" accent="#fb7185" />
        <Metric label="PM10" value={pm10} unit="µg/m³" accent="#60a5fa" />
        <Metric label="Temperature" value={temperature} unit="°C" accent="#c084fc" />
      </section>

      <section className="oriva-dash-panel">
        <h2>Monitoring overview</h2>
        <p className="oriva-dash-muted">
          {station != null ? `Station or location returned: ${station}` :
            "The current response did not expose a recognizable station name."}
        </p>
        <p className="oriva-dash-muted">
          Missing metric values are shown as unavailable; they are not inferred.
        </p>
      </section>

      <section className="oriva-dash-panel">
        <h2>Forecast stations</h2>
        {errors.forecast ? (
          <p className="oriva-dash-muted">Forecast station data could not be loaded.</p>
        ) : forecastRows.length ? (
          <div className="oriva-dash-table-wrap">
            <table className="oriva-dash-table">
              <thead><tr><th>Station</th><th>Available fields</th></tr></thead>
              <tbody>
                {forecastRows.slice(0, 12).map((row, index) => (
                  <tr key={index}>
                    <td>{row.station_name || row.station || row.name || `Station ${index + 1}`}</td>
                    <td>{Object.keys(row).slice(0, 6).join(", ") || "No fields"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="oriva-dash-muted">
            {loading ? "Loading forecast station list…" : "No forecast station list was returned in a recognized array format."}
          </p>
        )}
      </section>

      <details className="oriva-dash-panel">
        <summary style={{ cursor: "pointer", fontWeight: 700 }}>API response diagnostics</summary>
        <p className="oriva-dash-muted">Inspect the payloads used by this dashboard.</p>
        <pre className="oriva-dash-json">{JSON.stringify(data, null, 2)}</pre>
      </details>
    </main>
  );
}