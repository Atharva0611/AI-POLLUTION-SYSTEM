import React, { useEffect, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const DEFAULT_LOCATION = "Wagholi, Pune, Maharashtra, India";
const colors = { text: "#e8f0fc", muted: "#91a4bd", border: "#223650", blue: "#60a5fa", panel: "#101e32", bg: "#081321" };

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
        fetch(API_BASE + "/api/live/air-quality?location=" + encodeURIComponent(target), { cache: "no-store" }),
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
  const weatherapi = providers.weatherapi_air_quality || {};
  const components = aq.components || {};
  const readings = openaq.live_measurements || [];
  const findSensor = (name) => readings.find((x) => String(x.pollutant || "").toLowerCase() === name);
  const pm25 = weatherapi.status === "ok" && Number.isFinite(Number(weatherapi.pm2_5)) ? Number(weatherapi.pm2_5) : components.pm2_5 != null ? components.pm2_5 : findSensor("pm25") && findSensor("pm25").value;
  const pm10 = weatherapi.status === "ok" && Number.isFinite(Number(weatherapi.pm10)) ? Number(weatherapi.pm10) : components.pm10 != null ? components.pm10 : findSensor("pm10") && findSensor("pm10").value;
  const CPCB_BREAKPOINTS = {
    pm25: [[0,30,0,50],[30,60,50,100],[60,90,100,200],[90,120,200,300],[120,250,300,400],[250,Infinity,400,500]],
    pm10: [[0,50,0,50],[50,100,50,100],[100,250,100,200],[250,350,200,300],[350,430,300,400],[430,Infinity,400,500]],
    no2: [[0,40,0,50],[40,80,50,100],[80,180,100,200],[180,280,200,300],[280,400,300,400],[400,Infinity,400,500]],
    so2: [[0,40,0,50],[40,80,50,100],[80,380,100,200],[380,800,200,300],[800,1600,300,400],[1600,Infinity,400,500]],
    o3: [[0,50,0,50],[50,100,50,100],[100,168,100,200],[168,208,200,300],[208,748,300,400],[748,Infinity,400,500]],
    nh3: [[0,200,0,50],[200,400,50,100],[400,800,100,200],[800,1200,200,300],[1200,1800,300,400],[1800,Infinity,400,500]],
    co: [[0,1,0,50],[1,2,50,100],[2,10,100,200],[10,17,200,300],[17,34,300,400],[34,Infinity,400,500]]
  };

  const cpcbSubIndex = (rawValue, pollutant) => {
    const value = Number(rawValue);
    if (rawValue == null || !Number.isFinite(value) || value < 0) return null;
    const band = CPCB_BREAKPOINTS[pollutant].find(([low, high]) => value >= low && value <= high);
    if (!band) return null;
    const [clow, chigh, ilow, ihigh] = band;
    if (!Number.isFinite(chigh)) return 500;
    return Math.max(0, Math.min(500, Math.round(ilow + ((value - clow) / (chigh - clow)) * (ihigh - ilow))));
  };

  // Live values may not meet CPCB averaging-period requirements.
  // OpenWeather CO is converted from µg/m³ to mg/m³.
  const cpcbPollutants = [
    { name: "PM2.5", key: "pm25", value: pm25 },
    { name: "PM10", key: "pm10", value: pm10 },
    { name: "NO₂", key: "no2", value: components.no2 },
    { name: "SO₂", key: "so2", value: components.so2 },
    { name: "O₃", key: "o3", value: components.o3 },
    { name: "NH₃", key: "nh3", value: components.nh3 },
    { name: "CO", key: "co", value: components.co == null ? null : Number(components.co) / 1000 }
  ].map(p => ({ ...p, subIndex: cpcbSubIndex(p.value, p.key) }))
   .filter(p => p.subIndex !== null);

  const estimatedCpcbAQI = cpcbPollutants.length
    ? Math.max(...cpcbPollutants.map(p => p.subIndex))
    : null;

  const cpcbEstimateNote = cpcbPollutants.length >= 3 &&
    cpcbPollutants.some(p => p.key === "pm25" || p.key === "pm10")
    ? `Estimated CPCB-style AQI · ${cpcbPollutants.length} pollutants · averaging periods unverified`
    : `Indicative estimate only · ${cpcbPollutants.length} valid pollutants · CPCB data requirements not verified`;
  const metrics = [
    { label: "Estimated CPCB AQI", value: estimatedCpcbAQI, unit: "/ 500", note: cpcbEstimateNote, featured: true },
    { label: "PM2.5", value: pm25, unit: "Âµg/mÂ³", note: weatherapi.status === "ok" && weatherapi.pm2_5 != null ? "WeatherAPI current reading" : components.pm2_5 != null ? "OpenWeather current reading" : findSensor("pm25") ? "OpenAQ current sensor" : "No current observation" },
    { label: "PM10", value: pm10, unit: "Âµg/mÂ³", note: weatherapi.status === "ok" && weatherapi.pm10 != null ? "WeatherAPI current reading" : components.pm10 != null ? "OpenWeather current reading" : findSensor("pm10") ? "OpenAQ current sensor" : "No current observation" },
    { label: "Temperature", value: weather.status === "ok" ? weather.temperature_c : null, unit: "Â°C", note: weather.status === "ok" ? "OpenWeather current weather" : "No current weather reading" },
  ];
  const bars = [
    ["PM2.5", pm25], ["PM10", pm10], ["NOâ‚‚", components.no2], ["SOâ‚‚", components.so2], ["Oâ‚ƒ", components.o3], ["CO", components.co]
  ].filter((x) => x[1] != null && Number.isFinite(Number(x[1])));
  const max = Math.max(1, ...bars.map((x) => Number(x[1])));
  const card = { background: colors.panel, border: "1px solid " + colors.border, borderRadius: 18, padding: 22, minWidth: 0, boxShadow: "0 12px 32px rgba(0,0,0,.16)" };
  const label = { color: colors.muted, fontSize: 11, fontWeight: 750, letterSpacing: ".09em", textTransform: "uppercase" };
  const button = { border: 0, borderRadius: 10, padding: "12px 16px", background: colors.blue, color: "#fff", fontWeight: 700, cursor: "pointer" };
  const statusItems = [
    ["OpenWeather pollution", aq],
    ["OpenWeather weather", weather],
    ["OpenAQ sensors", openaq],
    ["WeatherAPI air quality", weatherapi]
  ];
  return <main style={{ padding: "clamp(18px,3vw,42px)", background: colors.bg, color: colors.text, minHeight: "100%", display: "grid", gap: 22, alignContent: "start", fontFamily: "Inter,Manrope,system-ui,sans-serif" }}>
    <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 18 }}>
      <div><div style={{ ...label, color: colors.blue }}>ORIVA / ENVIRONMENTAL INTELLIGENCE</div><h1 style={{ fontSize: "clamp(28px,3vw,40px)", letterSpacing: "-.045em", margin: "10px 0 8px" }}>Air quality overview</h1><p style={{ color: colors.muted, margin: 0, lineHeight: 1.6 }}>Location-specific conditions from connected providers, with source and freshness transparency.</p></div>
      <span style={{ color: colors.muted, fontSize: 12 }}>Last checked: {checkedAt || "Not checked"}</span>
    </header>
    <form onSubmit={(e) => { e.preventDefault(); if (query.trim()) refresh(query.trim()); }} style={{ ...card, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <label htmlFor="oriva-live-location" style={label}>Location</label><input id="oriva-live-location" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Enter Pune, Wagholi, or another locality" style={{ flex: "1 1 300px", minWidth: 0, border: "1px solid #ccd7e5", borderRadius: 10, padding: "12px 14px", color: "#17243a", background: "#ffffff", font: "inherit", opacity: 1, WebkitTextFillColor: "#17243a", caretColor: "#17243a" }} /><button type="submit" disabled={loading} style={button}>{loading ? "Loadingâ€¦" : "Update dashboard"}</button>
    </form>
    <div role="status" style={{ padding: 13, borderRadius: 10, border: "1px solid " + (error ? "#f1d8a8" : "#d7e5fc"), background: error ? "#fff7e8" : "#eaf2ff", color: error ? "#895b15" : "#2d5488", fontSize: 13 }}>{error || (loading ? "Fetching current provider dataâ€¦" : "Location: " + ((data && data.location && data.location.resolved_name) || location))}</div>
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 14 }}>
      {metrics.map((m) => <article key={m.label} style={{ ...card, ...(m.featured ? { background: "linear-gradient(135deg,#12365a,#075985 65%,#0f766e)", color: "#ffffff", border: "1px solid #2c7da0", boxShadow: "0 18px 42px rgba(0,0,0,.28)" } : {}) }}><div style={m.featured ? { ...label, color: "#c7e9ff" } : label}>{m.label}</div><div style={{ fontSize: "clamp(25px,2.5vw,36px)", fontWeight: 750, letterSpacing: "-.04em", margin: "14px 0 8px" }}>{m.value == null ? "â€”" : Number.isFinite(Number(m.value)) ? Number(m.value).toFixed(1) : m.value}<small style={{ fontSize: 12, color: m.featured ? "#c7e9ff" : colors.muted }}>{m.value == null ? "" : " " + m.unit}</small></div><div style={{ fontSize: 12, color: m.featured ? "#d6e9f8" : colors.muted }}>{m.note}</div></article>)}
    </section>
    <section style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}><div><div style={{ ...label, marginBottom: 8 }}>CURRENT POLLUTANT PROFILE</div><h2 style={{ fontSize: 19, margin: 0 }}>Pollutant concentration chart</h2></div><span style={{ fontSize: 12, color: colors.muted }}>Actual current provider values only</span></div>
      {bars.length ? bars.map(([name, value]) => <div key={name} style={{ display: "grid", gridTemplateColumns: "58px minmax(40px,1fr) 100px", gap: 12, alignItems: "center", margin: "18px 0", fontSize: 12 }}><strong>{name}</strong><div style={{ height: 9, borderRadius: 20, background: "#edf1f7", overflow: "hidden" }}><div style={{ height: "100%", width: Math.max(2, Number(value) / max * 100) + "%", borderRadius: 20, background: "linear-gradient(90deg,#3478d4,#58b6df)" }} /></div><span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{Number(value).toFixed(1)} Âµg/mÂ³</span></div>) : <p style={{ color: colors.muted, lineHeight: 1.6, fontSize: 13, marginTop: 18 }}>No eligible current pollutant concentrations were returned. This chart will populate when the providers return timestamp-validated readings; no synthetic or historical values are inserted.</p>}
      <p style={{ color: colors.muted, fontSize: 12, lineHeight: 1.6 }}>
        Pollutant values may come from OpenWeather, WeatherAPI, or OpenAQ depending on availability. Check each metric's source before comparing readings.
      </p>
      <p style={{ borderTop: "1px solid #e8edf4", paddingTop: 14, marginBottom: 0, color: colors.muted, fontSize: 12, lineHeight: 1.6 }}>This is a comparison of current concentrations, not a historical trend graph. Historical trend lines require timestamped historical observations.</p>
    </section>
    <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 14 }}>
      {statusItems.map(([name, item]) => <article key={name} style={card}><div style={label}>{name}</div><div style={{ fontSize: 15, fontWeight: 750, margin: "12px 0", color: item.status === "ok" || (item.fresh_count || 0) > 0 ? "#16794b" : "#9a6b18" }}>{item.status || "not checked"}</div><div style={{ color: colors.muted, fontSize: 12, lineHeight: 1.6 }}>{item.error || (item.status === "ok" ? "Current timestamp validated by backend." : (item.fresh_count || 0) + " eligible current sensor readings.")}</div></article>)}
    </section>
    <section style={{ ...card, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}><div><div style={label}>MODEL OUTPUTS</div><h2 style={{ fontSize: 19, margin: "8px 0" }}>Forecast and spatial analysis</h2><p style={{ color: colors.muted, fontSize: 12, margin: 0 }}>Forecast station records: {forecastCount == null ? "unavailable" : forecastCount}. Model outputs and historical hotspots are kept separate from live readings.</p></div><div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button style={button} onClick={() => setView("dashboard")}>Forecast explorer</button><button style={{ ...button, background: "#e8eef7", color: "#26374f" }} onClick={() => setView("map")}>Hotspot map</button><button style={{ ...button, background: "#e8eef7", color: "#26374f" }} onClick={() => setView("chat")}>Ask ORIVA</button></div></section>
    <footer style={{ color: colors.muted, fontSize: 12 }}>Requested location: {location} Â· Observation time: {aq.observed_at || weatherapi.observed_at || weather.observed_at || "No current timestamp returned"} Â· Response checked: {data && data.updated_at ? new Date(data.updated_at).toLocaleString() : "â€”"}</footer>
  </main>;
}


