import { useCallback, useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const PALETTE = { good: "#15803d", moderate: "#ca8a04", unhealthy_sensitive: "#ea580c", unhealthy: "#dc2626", very_unhealthy: "#7e22ce", hazardous: "#7f1d1d", unavailable: "#64748b" };

function FitStations({ stations }) {
  const map = useMap();
  useEffect(() => {
    const points = stations.filter(s => Number.isFinite(Number(s.latitude)) && Number.isFinite(Number(s.longitude))).map(s => [Number(s.latitude), Number(s.longitude)]);
    if (points.length === 1) map.setView(points[0], 13);
    else if (points.length > 1) map.fitBounds(points, { padding: [35, 35], maxZoom: 13 });
  }, [stations, map]);
  return null;
}
const number = (value, digits = 1) => value === null || value === undefined || value === "" || !Number.isFinite(Number(value)) ? "Unavailable" : Number(value).toFixed(digits);
const severityColor = s => PALETTE[s] || PALETTE.unavailable;

export default function Hotspots() {
  const [mode, setMode] = useState("live");
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [selected, setSelected] = useState(null);
  const [updatedAt, setUpdatedAt] = useState("");
  const [apiMessage, setApiMessage] = useState("");

  const loadStations = useCallback(async (selectedMode = mode) => {
    setLoading(true); setError(""); setSelected(null);
    const url = selectedMode === "live" ? API_BASE + "/api/hotspots/live" : API_BASE + "/api/hotspots/";
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(90000) });
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Hotspot API returned HTTP " + response.status);
      const rows = selectedMode === "live" ? payload.stations : payload.hotspots;
      if (!Array.isArray(rows)) throw new Error("API response did not contain a station list.");
      setStations(rows);
      setApiMessage(payload.message || "");
      setUpdatedAt(new Date().toLocaleString());
    } catch (err) {
      setStations([]);
      setError((err.message || "Request failed") + ". Confirm FastAPI is running at " + API_BASE + ".");
    } finally { setLoading(false); }
  }, [mode]);

  useEffect(() => { loadStations(mode); }, [mode, loadStations]);

  const validStations = useMemo(() => stations.filter(s =>
    Number.isFinite(Number(s.latitude)) && Number.isFinite(Number(s.longitude)) &&
    Number(s.latitude) >= -90 && Number(s.latitude) <= 90 &&
    Number(s.longitude) >= -180 && Number(s.longitude) <= 180
  ), [stations]);

  const filtered = useMemo(() => validStations.filter(s => {
    const label = String(s.station_name || s.resolved_location || s.requested_location || "");
    const matchName = label.toLowerCase().includes(search.toLowerCase().trim());
    const matchSeverity = severity === "all" || (mode === "live" ? (s.severity || "unavailable") === severity : severity === "unavailable" ? false : String(s.pollution_level || "").toLowerCase() === severity);
    const matchSource = sourceFilter === "all" || String(s.source || (mode === "historical" ? "Historical CPCB dataset" : "")).toLowerCase().includes(sourceFilter.toLowerCase());
    return matchName && matchSeverity && matchSource;
  }), [validStations, search, severity, sourceFilter, mode]);

  const liveSuccess = stations.filter(s => s.status === "ok").length;
  const colorFor = station => mode === "live" ? severityColor(station.severity) : Number(station.cluster) === -1 ? "#ca8a04" : "#2563eb";

  return (
    <main className="oriva-hotspots" style={styles.page}>
      <style>{`.oriva-hotspots select,.oriva-hotspots input{font:inherit;color:#172033;background:#fff;border:1px solid #cbd5e1;border-radius:9px;padding:10px 12px;min-width:0}.oriva-hotspots button{cursor:pointer}.oriva-hotspots button:focus-visible,.oriva-hotspots input:focus-visible,.oriva-hotspots select:focus-visible{outline:2px solid #2563eb;outline-offset:2px}@media(max-width:700px){.oriva-hotspots .filters{grid-template-columns:1fr!important}.oriva-hotspots .stats{grid-template-columns:1fr 1fr!important}}`}</style>
      <header style={styles.header}>
        <div><div style={styles.eyebrow}>ORIVA / SPATIAL INTELLIGENCE</div><h1 style={styles.title}>Environmental hotspot explorer</h1><p style={styles.muted}>Compare provider-based current environmental conditions with historical DBSCAN station clusters.</p></div>
        <button style={styles.button} onClick={() => loadStations(mode)} disabled={loading}>{loading ? "Loading…" : "↻ Refresh layer"}</button>
      </header>
      <section style={styles.panel}>
        <div style={styles.modeRow} role="group" aria-label="Map data layer">
          <button aria-pressed={mode === "live"} style={mode === "live" ? styles.activeTab : styles.tab} onClick={() => setMode("live")}>Live environmental data</button>
          <button aria-pressed={mode === "historical"} style={mode === "historical" ? styles.activeTab : styles.tab} onClick={() => setMode("historical")}>Historical DBSCAN</button>
        </div>
        <p style={styles.disclaimer}>{mode === "live" ? "Live provider data or atmospheric-model estimates. WeatherAPI's US EPA index is a 1–6 category index, not a numeric AQI; Open-Meteo numeric AQI uses the US AQI scale. Neither is labelled as official CPCB station data." : "Historical station clusters from the processed Pune CPCB dataset. Refreshing reloads the dataset; it does not make measurements live."}</p>
        {mode === "live" && <div style={styles.stats} className="stats">
          <Metric label="Locations listed" value={stations.length}/>
          <Metric label="Successful data results" value={liveSuccess}/>
          <Metric label="No AQI available" value={stations.filter(s => s.aqi === null || s.aqi === undefined).length}/>
        </div>}
        <div className="filters" style={styles.filters}>
          <input aria-label="Search station" placeholder="Search locality / station…" value={search} onChange={e => setSearch(e.target.value)}/>
          <select aria-label="Filter severity" value={severity} onChange={e => setSeverity(e.target.value)}>
            <option value="all">All severity levels</option><option value="good">Good</option><option value="moderate">Moderate</option><option value="unhealthy_sensitive">Unhealthy for sensitive groups</option><option value="unhealthy">Unhealthy</option><option value="very_unhealthy">Very unhealthy</option><option value="hazardous">Hazardous</option><option value="unavailable">Unavailable</option>
          </select>
          <select aria-label="Filter data source" value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}>
            <option value="all">All sources</option><option value="WeatherAPI">WeatherAPI</option><option value="Open-Meteo">Open-Meteo</option><option value="historical">Historical dataset</option>
          </select>
        </div>
        {error && <div role="alert" style={styles.error}>{error}<button style={styles.retry} onClick={() => loadStations(mode)}>Retry</button></div>}
        {loading && <p style={styles.empty}>Fetching {mode === "live" ? "each location independently" : "historical station clusters"}…</p>}
        {!loading && !error && filtered.length === 0 && <p style={styles.empty}>No stations match these filters, or the selected data layer returned no valid coordinates.</p>}
        {filtered.length > 0 && <MapContainer key={mode} center={[18.52, 73.86]} zoom={11} scrollWheelZoom style={styles.map}>
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
          <FitStations stations={filtered}/>
          {filtered.map((s, i) => <CircleMarker key={(s.requested_location || s.station_name || "station") + i} center={[Number(s.latitude), Number(s.longitude)]} radius={selected === s ? 11 : 8} pathOptions={{ color: colorFor(s), fillColor: colorFor(s), fillOpacity: .8, weight: 2 }} eventHandlers={{ click: () => setSelected(s) }}>
            <Popup><strong>{s.station_name || s.resolved_location || s.requested_location}</strong>{mode === "live" ? <>
              <p>AQI / index: {number(s.aqi, 0)} {s.aqi_scale || ""}</p><p>Severity: {String(s.severity || "unavailable").replaceAll("_", " ")}</p><p>PM2.5: {number(s.pm2_5)} µg/m³ · PM10: {number(s.pm10)} µg/m³</p><p>Temperature: {number(s.weather?.temperature_c)} °C · Wind: {number(s.weather?.wind_speed_kph)} km/h</p><p>Source: {s.source || "Unavailable"} · {s.timestamp || "Timestamp unavailable"}</p><small>{(s.warnings || []).join(" ")}</small>
            </> : <><p>Historical mean PM2.5: {number(s.pm25_mean)} µg/m³</p><p>Historical maximum PM2.5: {number(s.pm25_max)} µg/m³</p><p>DBSCAN cluster: {s.cluster}</p><small>Historical data; not a live reading.</small></>}</Popup>
          </CircleMarker>)}
        </MapContainer>}
      </section>
      <section style={styles.panel}>
        <div style={styles.tableHeading}><div><h2 style={styles.heading}>Location details</h2><p style={styles.muted}>{filtered.length} records match current filters.</p></div><span style={styles.timestamp}>Last fetched: {updatedAt || "Not loaded"}</span></div>
        <div style={{overflowX:"auto"}}><table style={styles.table}><thead><tr>{(mode === "live" ? ["Location","AQI / index","PM2.5","PM10","Severity","Provider","Updated"] : ["Station","Mean PM2.5","Max PM2.5","Cluster","Classification","Source"]).map(h => <th key={h} style={styles.th}>{h}</th>)}</tr></thead>
          <tbody>{filtered.map((s,i) => <tr key={(s.requested_location || s.station_name || "row")+i} onClick={() => setSelected(s)} style={{cursor:"pointer",background:selected===s?"#eff6ff":"transparent"}}>
            {mode === "live" ? <><td style={styles.td}>{s.station_name || s.resolved_location || s.requested_location}</td><td style={styles.td}>{number(s.aqi,0)} {s.aqi_scale || ""}</td><td style={styles.td}>{number(s.pm2_5)}</td><td style={styles.td}>{number(s.pm10)}</td><td style={styles.td}><span style={{...styles.pill,color:colorFor(s)}}>{String(s.severity || s.status || "unavailable").replaceAll("_"," ")}</span></td><td style={styles.td}>{s.source || "Unavailable"}</td><td style={styles.td}>{s.timestamp || "Unavailable"}</td></> : <><td style={styles.td}>{s.station_name}</td><td style={styles.td}>{number(s.pm25_mean)}</td><td style={styles.td}>{number(s.pm25_max)}</td><td style={styles.td}>{s.cluster ?? "N/A"}</td><td style={styles.td}>{s.pollution_level || (Number(s.cluster)===-1?"Noise":"Cluster member")}</td><td style={styles.td}>Historical CPCB dataset</td></>}
          </tr>)}</tbody></table></div>
        {selected && <div style={styles.selected}><strong>Selected: {selected.station_name || selected.resolved_location || selected.requested_location}</strong><span>Coordinates: {number(selected.latitude,5)}, {number(selected.longitude,5)} · {mode === "live" ? (selected.warnings || []).join(" ") : "Historical DBSCAN data; not a live reading."}</span></div>}
      </section>
      <div style={styles.legend}><strong>Map legend</strong>{(mode === "live" ? [["good","Good"],["moderate","Moderate"],["unhealthy_sensitive","Unhealthy for sensitive groups"],["unhealthy","Unhealthy"],["very_unhealthy","Very unhealthy"],["hazardous","Hazardous"],["unavailable","Unavailable"]] : [["cluster","DBSCAN cluster member"],["noise","DBSCAN noise"]]).map(([key,label]) => <span key={key} style={styles.legendItem}><i style={{background:mode==="live"?severityColor(key):key==="noise"?"#ca8a04":"#2563eb"}}/>{label}</span>)}</div>
      <footer style={styles.footer}>{apiMessage} Sources: <a href="https://www.weatherapi.com/docs/" target="_blank" rel="noreferrer">WeatherAPI documentation</a> · <a href="https://open-meteo.com/en/docs/air-quality-api" target="_blank" rel="noreferrer">Open-Meteo Air Quality API</a> · Map tiles © OpenStreetMap contributors. {mode === "live" ? "Weather conditions provide context only and do not alter AQI severity." : "Historical DBSCAN clusters are separate from the live layer."}</footer>
    </main>
  );
}

function Metric({label,value}) { return <div style={styles.metric}><span style={styles.muted}>{label}</span><strong style={{fontSize:25,color:"#172033"}}>{value}</strong></div>; }

const styles = {
  page:{color:"#172033",padding:"clamp(16px,3vw,30px)",display:"grid",gap:18,minWidth:0,background:"#f8fafc"},
  header:{display:"flex",justifyContent:"space-between",alignItems:"center",gap:16,flexWrap:"wrap"},
  eyebrow:{color:"#475569",fontSize:11,fontWeight:800,letterSpacing:".15em"},
  title:{fontSize:"clamp(25px,3vw,36px)",margin:"8px 0",letterSpacing:"-.03em"},
  muted:{color:"#64748b",fontSize:13,margin:"5px 0",lineHeight:1.6},
  button:{border:"1px solid #1d4ed8",borderRadius:10,padding:"11px 16px",color:"#fff",background:"#1d4ed8",cursor:"pointer",fontWeight:750},
  panel:{background:"#fff",border:"1px solid #e2e8f0",borderRadius:16,overflow:"hidden",padding:16,display:"grid",gap:14},
  modeRow:{display:"flex",gap:8,flexWrap:"wrap"},
  tab:{border:"1px solid #cbd5e1",background:"#fff",color:"#334155",padding:"10px 14px",borderRadius:9,fontWeight:700},
  activeTab:{border:"1px solid #1d4ed8",background:"#eff6ff",color:"#1d4ed8",padding:"10px 14px",borderRadius:9,fontWeight:800},
  disclaimer:{margin:0,padding:13,borderRadius:10,background:"#eff6ff",color:"#334155",fontSize:12,lineHeight:1.65},
  stats:{display:"grid",gridTemplateColumns:"repeat(3,minmax(0,1fr))",gap:10},
  metric:{display:"grid",gap:8,padding:14,borderRadius:11,border:"1px solid #e2e8f0",background:"#fff"},
  filters:{display:"grid",gridTemplateColumns:"minmax(160px,1fr) minmax(180px,.8fr) minmax(180px,.8fr)",gap:10},
  map:{height:480,width:"100%",background:"#e2e8f0",zIndex:1,borderRadius:10},
  empty:{padding:24,textAlign:"center",color:"#64748b",background:"#f8fafc",borderRadius:10},
  error:{padding:14,borderRadius:10,color:"#991b1b",background:"#fef2f2",border:"1px solid #fecaca",display:"flex",justifyContent:"space-between",gap:12,flexWrap:"wrap"},
  retry:{padding:"6px 10px",borderRadius:8,border:"1px solid #dc2626",background:"#fff",color:"#991b1b"},
  tableHeading:{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12,flexWrap:"wrap"},
  heading:{fontSize:17,margin:0,color:"#172033"},
  timestamp:{fontSize:11,color:"#64748b"},
  table:{width:"100%",borderCollapse:"collapse",textAlign:"left",fontSize:12},
  th:{padding:12,whiteSpace:"nowrap",color:"#475569",borderBottom:"1px solid #e2e8f0",background:"#f8fafc"},
  td:{padding:12,whiteSpace:"nowrap",borderBottom:"1px solid #f1f5f9",color:"#334155"},
  pill:{fontSize:11,fontWeight:750,textTransform:"capitalize"},
  selected:{padding:13,display:"grid",gap:6,color:"#475569",fontSize:12,background:"#f8fafc",borderRadius:10},
  legend:{display:"flex",gap:12,flexWrap:"wrap",alignItems:"center",fontSize:11,color:"#475569"},
  legendItem:{display:"inline-flex",alignItems:"center",gap:5},
  footer:{color:"#64748b",fontSize:11,lineHeight:1.7},
};
