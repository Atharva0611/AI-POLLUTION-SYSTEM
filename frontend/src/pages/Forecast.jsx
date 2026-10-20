import React, { useCallback, useEffect, useMemo, useState } from "react";

const API = `${(import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "")}/api/forecast/universal`;
const num = (v, d = 1) => Number.isFinite(Number(v)) ? Number(v).toFixed(d) : "—";

function rowsFromShap(shap) {
  if (Array.isArray(shap)) return shap;
  if (!shap || typeof shap !== "object") return [];
  for (const key of ["features", "contributions", "top_features", "feature_importance"]) {
    if (Array.isArray(shap[key])) return shap[key];
  }
  if (shap.values && typeof shap.values === "object" && !Array.isArray(shap.values)) {
    return Object.entries(shap.values).map(([feature, value]) => ({ feature, value }));
  }
  return [];
}

export default function Forecast() {
  const [draft, setDraft] = useState("Pune");
  const [location, setLocation] = useState("Pune");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = useCallback(async (target) => {
    const q = target.trim();
    if (!q) return setError("Enter a city or locality.");
    setLoading(true); setError(""); setData(null); setLocation(q);
    try {
      const response = await fetch(`${API}?location=${encodeURIComponent(q)}`);
      const body = await response.json().catch(() => ({}));
      if (!response.ok || body.status === "error") throw new Error(body.detail || body.message || `HTTP ${response.status}`);
      setData(body);
    } catch (e) {
      setError(`${e.message}. Check that the backend is running.`);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { run("Pune"); }, [run]);
  const shapRows = useMemo(() => rowsFromShap(data?.shap_explanation || data?.shap_contributions || data?.shap), [data]);
  const stations = Array.isArray(data?.contributing_stations) ? data.contributing_stations : [];
  const hourly = Array.isArray(data?.hourly_context) ? data.hourly_context : [];
  const predictionOK = data?.forecast_available === true && data?.predicted_pm25 != null && Number.isFinite(Number(data.predicted_pm25));
  const modelGenerated = data?.model_generated === true || ["DIRECT_STATION_FORECAST", "SPATIALLY_ESTIMATED_FORECAST"].includes(data?.forecast_method);
  const method = data?.forecast_method_label || data?.forecast_method || (modelGenerated ? "Model forecast" : "Method not specified");

  return <div className="forecast-page">
    <header className="forecast-header">
      <div><div className="aq-eyebrow">PREDICTIVE ANALYTICS / MODEL TRANSPARENCY</div><h1>PM2.5 Forecast &amp; Explainability</h1><p>Inspect next-hour prediction, station coverage, hourly context, and SHAP values returned by the backend.</p></div>
      <form className="forecast-search" onSubmit={e => { e.preventDefault(); run(draft); }}>
        <label htmlFor="forecast-location">City or locality</label><div className="forecast-search-row"><input id="forecast-location" value={draft} onChange={e => setDraft(e.target.value)} placeholder="Enter location"/><button className="aq-button" disabled={loading || !draft.trim()}>{loading ? "Loading…" : "Run forecast"}</button></div>
      </form>
    </header>
    <div className="forecast-notice"><strong>Source distinction</strong><span>A provider hourly estimate is not an XGBoost prediction. This page labels the result using the method and flags returned by the API; it does not infer official CPCB AQI.</span></div>
    {error && <div className="aq-error" role="alert">{error}</div>}
    {loading && <div className="forecast-loading" role="status">Loading forecast for {location}…</div>}
    {!loading && data && <>
      <section className="forecast-metrics">
        <article className="forecast-metric forecast-metric-primary"><span>Next-hour PM2.5</span><strong>{predictionOK ? num(data.predicted_pm25, 2) : "Unavailable"}</strong><small>µg/m³ · {modelGenerated ? "Model-generated" : "Non-model/provider result"}</small></article>
        <article className="forecast-metric"><span>Requested location</span><strong>{data.requested_location || location}</strong><small>API input</small></article>
        <article className="forecast-metric"><span>Forecast method</span><strong className="forecast-method-value">{method}</strong><small>{data.fallback_used ? "Fallback used" : "Fallback not flagged"}</small></article>
        <article className="forecast-metric"><span>Contributing stations</span><strong>{stations.length}</strong><small>Returned by API</small></article>
      </section>
      {!predictionOK && <div className="forecast-empty"><strong>Forecast unavailable</strong><p>{data.reason || "No valid prediction was returned. Check station coverage, model artifacts, and backend logs."}</p></div>}
      {data.reason && predictionOK && <p className="forecast-reason">{data.reason}</p>}
      <section className="forecast-provenance">
        <div><span>Model / service</span><strong>{data.model_name || "Not reported"}</strong><small>{data.model_version ? `Version ${data.model_version}` : "Version not supplied"}</small></div>
        <div><span>Forecast case</span><strong>{data.case || "Not reported"}</strong><small>{data.data_quality_status || "Quality status unavailable"}</small></div>
        <div><span>Reported validation R²</span><strong>{data.validation_metrics?.holdout_r2 == null ? "Unavailable" : num(data.validation_metrics.holdout_r2, 3)}</strong><small>Chronological holdout metric, if present</small></div>
        <div><span>Reported holdout MAE</span><strong>{data.validation_metrics?.holdout_mae == null ? "Unavailable" : `${num(data.validation_metrics.holdout_mae, 2)} µg/m³`}</strong><small>Not a guarantee for this location</small></div>
      </section>
      {Array.isArray(data.warnings) && data.warnings.length > 0 && <section className="forecast-warnings"><strong>Data-quality warnings</strong><ul>{data.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></section>}
      <section className="forecast-panels">
        <article className="forecast-panel"><div className="forecast-panel-heading"><div><h2>SHAP explainability</h2><p>Feature contributions supplied by the backend</p></div><span className="forecast-tag">{shapRows.length ? `${shapRows.length} entries` : "No SHAP data"}</span></div>
          {shapRows.length ? <div className="forecast-shap-list">{shapRows.slice(0, 12).map((row, i) => {
            const name = typeof row === "string" ? row : row?.feature || row?.name || row?.feature_name || row?.label || `Feature ${i + 1}`;
            const raw = typeof row === "number" ? row : row?.shap_value ?? row?.contribution ?? row?.value ?? row?.importance ?? row?.impact;
            const value = raw == null || !Number.isFinite(Number(raw)) ? null : Number(raw);
            const max = Math.max(1, ...shapRows.map(r => Number(typeof r === "number" ? r : r?.shap_value ?? r?.contribution ?? r?.value ?? r?.importance ?? r?.impact)).filter(Number.isFinite).map(Math.abs));
            return <div className="forecast-shap-row" key={`${name}-${i}`}><div className="forecast-shap-label"><span>{name}</span><strong>{value == null ? "Value unavailable" : value.toFixed(4)}</strong></div>{value != null && <div className="forecast-bar-track"><div className={`forecast-bar ${value >= 0 ? "positive" : "negative"}`} style={{width:`${Math.min(100, Math.abs(value)/max*100)}%`}}/></div>}</div>;
          })}</div> : <div className="forecast-empty"><strong>SHAP values not returned</strong><p>No recognized feature-contribution list was found. Missing SHAP data is not interpreted as zero impact.</p></div>}
          {data.shap_explanation?.summary && <p className="forecast-reason">{data.shap_explanation.summary}</p>}
        </article>
        <article className="forecast-panel"><div className="forecast-panel-heading"><div><h2>Station coverage</h2><p>Stations considered by the forecasting service</p></div><span className="forecast-tag">{stations.length} returned</span></div>
          {stations.length ? <div className="forecast-table-wrap"><table className="aq-table"><thead><tr><th>Station</th><th>Distance</th><th>Observation time</th></tr></thead><tbody>{stations.map((s,i)=><tr key={s.station_id || s.id || i}><td><strong>{s.name || s.station_name || s.station || "Unnamed station"}</strong><small>{s.city || s.state || s.source || ""}</small></td><td>{s.distance_km == null ? "—" : `${num(s.distance_km,2)} km`}</td><td>{s.timestamp || s.observed_at || s.last_updated || "Not supplied"}</td></tr>)}</tbody></table></div> : <div className="forecast-empty">No contributing station list was returned.</div>}
        </article>
      </section>
      <section className="forecast-panel"><div className="forecast-panel-heading"><div><h2>Hourly context</h2><p>Environmental-provider context, separate from the next-hour forecast</p></div><span className="forecast-tag">{hourly.length} records</span></div>
        {hourly.length ? <div className="forecast-table-wrap"><table className="aq-table"><thead><tr><th>Time</th><th>PM2.5</th><th>Temperature</th><th>Humidity</th><th>Wind speed</th></tr></thead><tbody>{hourly.slice(0,24).map((h,i)=><tr key={h.time || h.timestamp || i}><td>{h.time || h.timestamp || h.datetime || `Hour ${i+1}`}</td><td>{num(h.pm2_5_estimate ?? h.pm25_estimate ?? h.pm2_5 ?? h.pm25)}</td><td>{num(h.temperature_2m ?? h.temperature ?? h.temp_c)}</td><td>{num(h.relative_humidity_2m ?? h.humidity,0)}</td><td>{num(h.wind_speed_10m ?? h.wind_speed ?? h.wind_kph)}</td></tr>)}</tbody></table></div> : <div className="forecast-empty">No hourly context returned.</div>}
      </section>
      <footer className="forecast-footer">Rendered from the API response. Missing fields remain unavailable. Validate model performance and source timestamps before operational use.</footer>
    </>}
  </div>;
}
