import React, { useEffect, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8003").replace(/\/$/, "");
const DEFAULT_LOCATION = "Wagholi, Pune, Maharashtra, India";
const colors = { text: "#17243a", muted: "#68788f", border: "#dce4ee", blue: "#2868c7", panel: "#ffffff", bg: "#f4f7fb" };

export default function LiveOverview({ setView }) {
  const [query, setQuery] = useState(DEFAULT_LOCATION);
  const [location, setLocation] = useState(DEFAULT_LOCATION);
  const [data, setData] = useState(null);
  const [forecastCount, setForecastCount] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [checkedAt, setCheckedAt] = useState("");

  async function refresh(target) {
    setLoading(true); setError("");
    try {
      const responses = await Promise.all([
        fetch(API_BASE + "/api/live/air-quality?location=" + encodeURIComponent(target)),
        fetch(API_BASE + "/api/forecast/stations").catch(() => null)
      ]);
      const body = await responses[0].json().catch(() => ({}));
      if (!responses[0].ok) throw new Error(body.detail || "Live API returned HTTP " + responses[0].status);
      setData(body); setLocation(target); setCheckedAt(new Date().toLocaleTimeString());
      if (responses[1] && responses[1].ok) {
        const f = await responses[1].json().catch(() => null);
        const rows = Array.isArray(f) ? f : Object.values(f || {}).find(Array.isArray) || [];
        setForecastCount(rows.length);
      } else setForecastCount(null);
      const p = body.providers || {};
      if (body.status !== "ok") setError("No verified current observations returned. Check the provider status cards below.");
      else if (!(p.openweather_air_pollution || {}).status || (p.openweather_air_pollution || {}).status !== "ok") setError("Some providers are unavailable; showing only eligible readings from providers that responded.");
    } catch (e) {
      setData(null); setError((e.message || "Live data request failed") + ". Confirm the backend is running and provider keys are configured."); setCheckedAt(new Date().toLocaleTimeString());
    } finally { setLoading(false); }
  }

  useEffect(() => { refresh(DEFAULT_LOCATION); }, []);
  const providers = data && data.providers || {};
  const aq = providers.openweather_air_pollution || {};
  const weather = providers.openweather_weather || {};
  const openaq = providers.openaq || {};
  const components = aq.components || {};
  const readings = openaq.live_measurements || [];
  const findSensor = (name) => readings.find((x) => String(x.pollutant || "").toLowerCase() === name);
  const pm25 = components.pm2_5 != null ? components.pm2_5 : findSensor("pm25") && findSensor("pm25").value;
  const pm10 = components.pm10 != null ? components.pm10 : findSensor("pm10") && findSensor("pm10").value;
  const metrics = [
    { label: "OpenWeather AQI", value: aq.status === "ok" ? aq.aqi : null, unit: "/ 5", note: "OpenWeather scale Â· not CPCB AQI" },
    { label: "PM2.5", value: pm25, unit: "Âµg/mÂ³", note: components.pm2_5 != null ? "OpenWeather current reading" : findSensor("pm25") ? "OpenAQ current sensor" : "No current observation" },
    { label: "PM10", value: pm10, unit: "Âµg/mÂ³", note: components.pm10 != null ? "OpenWeather current reading" : findSensor("pm10") ? "OpenAQ current sensor" : "No current observation" },
    { label: "Temperature", value: weather.status === "ok" ? weather.temperature_c : null, unit: "Â°C", note: weather.status === "ok" ? "OpenWeather current weather" : "No current weather reading" }
  ];
  const bars = [
    ["PM2.5", pm25], ["PM10", pm10], ["NOâ‚‚", components.no2], ["SOâ‚‚", components.so2], ["Oâ‚ƒ", components.o3], ["CO", components.co]
  ].filter((x) => x[1] != null && Number.isFinite(Number(x[1])));
  const max = Math.max(1, ...bars.map((x) => Number(x[1])));
  const card = { background: colors.panel, border: "1px solid " + colors.border, borderRadius: 16, padding: 20, minWidth: 0, boxShadow: "0 8px 26px rgba(24,39,75,.045)" };
  const label = { color: colors.muted, fontSize: 11, fontWeight: 750, letterSpacing: ".09em", textTransform: "uppercase" };
  const button = { border: 0, borderRadius: 10, padding: "12px 16px", background: colors.blue, color: "#fff", fontWeight: 700, cursor: "pointer" };
  const statusItems = [
    ["OpenWeather pollution", aq],
    ["OpenWeather weather", weather],
    ["OpenAQ sensors", openaq]
  ];
  return <main className="oriva-live-overview" style={{ padding: "clamp(18px,3vw,42px)", background: colors.bg, color: colors.text, minHeight: "100%", display: "grid", gap: 22, alignContent: "start", fontFamily: "Inter,Manrope,system-ui,sans-serif" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 18 }}>
      <div><div style={{ ...label, color: colors.blue }}>ORIVA / ENVIRONMENTAL INTELLIGENCE</div><h1 style={{ fontSize: "clamp(28px,3vw,40px)", letterSpacing: "-.045em", margin: "10px 0 8px" }}>Air quality overview</h1><p style={{ color: colors.muted, margin: 0, lineHeight: 1.6 }}>Location-specific conditions from connected providers, with source and freshness transparency.</p></div>
      <span style={{ color: colors.muted, fontSize: 12 }}>Last checked: {checkedAt || "Not checked"}</span>
    </header>
    <form onSubmit={(e) => { e.preventDefault(); if (query.trim()) refresh(query.trim()); }} style={{ ...card, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <label htmlFor="oriva-live-location" style={label}>Location</label><input id="oriva-live-location" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Enter Pune, Wagholi, or another locality" style={{ flex: "1 1 300px", minWidth: 0, border: "1px solid #ccd7e5", borderRadius: 10, padding: "12px 14px", color: colors.text, background: "#fff", font: "inherit" }} /><button type="submit" disabled={loading} style={button}>{loading ? "Loadingâ€¦" : "Update dashboard"}</button>
    </form>
    <div role="status" style={{ padding: 13, borderRadius: 10, border: "1px solid " + (error ? "#f1d8a8" : "#d7e5fc"), background: error ? "#fff7e8" : "#eaf2ff", color: error ? "#895b15" : "#2d5488", fontSize: 13 }}>{error || (loading ? "Fetching current provider dataâ€¦" : "Location: " + ((data && data.location && data.location.resolved_name) || location))}</div>
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 14 }}>
      {metrics.map((m) => <article key={m.label} style={card}><div style={label}>{m.label}</div><div style={{ fontSize: "clamp(25px,2.5vw,36px)", fontWeight: 750, letterSpacing: "-.04em", margin: "14px 0 8px" }}>{m.value == null ? "â€”" : Number.isFinite(Number(m.value)) ? Number(m.value).toFixed(1) : m.value}<small style={{ fontSize: 12, color: colors.muted }}>{m.value == null ? "" : " " + m.unit}</small></div><div style={{ fontSize: 12, color: colors.muted }}>{m.note}</div></article>)}
    </section>
    <section style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}><div><div style={{ ...label, marginBottom: 8 }}>CURRENT POLLUTANT PROFILE</div><h2 style={{ fontSize: 19, margin: 0 }}>Pollutant concentration chart</h2></div><span style={{ fontSize: 12, color: colors.muted }}>Actual current provider values only</span></div>
      {bars.length ? bars.map(([name, value]) => <div key={name} style={{ display: "grid", gridTemplateColumns: "58px minmax(40px,1fr) 100px", gap: 12, alignItems: "center", margin: "18px 0", fontSize: 12 }}><strong>{name}</strong><div style={{ height: 9, borderRadius: 20, background: "#edf1f7", overflow: "hidden" }}><div style={{ height: "100%", width: Math.max(2, Number(value) / max * 100) + "%", borderRadius: 20, background: "linear-gradient(90deg,#3478d4,#58b6df)" }} /></div><span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{Number(value).toFixed(1)} Âµg/mÂ³</span></div>) : <p style={{ color: colors.muted, lineHeight: 1.6, fontSize: 13, marginTop: 18 }}>No eligible current pollutant concentrations were returned. This chart will populate when the providers return timestamp-validated readings; no synthetic or historical values are inserted.</p>}
      <p style={{ borderTop: "1px solid #e8edf4", paddingTop: 14, marginBottom: 0, color: colors.muted, fontSize: 12, lineHeight: 1.6 }}>This is a comparison of current concentrations, not a historical trend graph. Historical trend lines require timestamped historical observations.</p>
    </section>
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 14 }}>
      {statusItems.map(([name, item]) => <article key={name} style={card}><div style={label}>{name}</div><div style={{ fontSize: 15, fontWeight: 750, margin: "12px 0", color: item.status === "ok" || (item.fresh_count || 0) > 0 ? "#16794b" : "#9a6b18" }}>{item.status || "not checked"}</div><div style={{ color: colors.muted, fontSize: 12, lineHeight: 1.6 }}>{item.error || (item.status === "ok" ? "Current timestamp validated by backend." : (item.fresh_count || 0) + " eligible current sensor readings.")}</div></article>)}
    </section>
    <section style={{ ...card, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}><div><div style={label}>MODEL OUTPUTS</div><h2 style={{ fontSize: 19, margin: "8px 0" }}>Forecast and spatial analysis</h2><p style={{ color: colors.muted, fontSize: 12, margin: 0 }}>Forecast station records: {forecastCount == null ? "unavailable" : forecastCount}. Model outputs and historical hotspots are kept separate from live readings.</p></div><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button style={button} onClick={() => setView("forecast")}>Forecast explorer</button><button style={{ ...button, background: "#e8eef7", color: "#26374f" }} onClick={() => setView("map")}>Hotspot map</button><button style={{ ...button, background: "#e8eef7", color: "#26374f" }} onClick={() => setView("chat")}>Ask ORIVA</button></div></section>
    <footer style={{ color: colors.muted, fontSize: 12 }}>Requested location: {location} Â· Observation time: {aq.observed_at || weather.observed_at || "No current timestamp returned"} Â· Response checked: {data && data.updated_at ? new Date(data.updated_at).toLocaleString() : "â€”"}</footer>
  </main>;
}
