import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Circle,
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8003").replace(/\/$/, "");
const API_URL = API_BASE + "/api/hotspots/";
const PUNE_CENTER = [18.5204, 73.8567];

function FitStations({ stations }) {
  const map = useMap();
  useEffect(() => {
    const points = stations
      .filter(s => Number.isFinite(Number(s.latitude)) && Number.isFinite(Number(s.longitude)))
      .map(s => [Number(s.latitude), Number(s.longitude)]);
    if (points.length > 1) map.fitBounds(points, { padding: [35, 35], maxZoom: 12 });
    else if (points.length === 1) map.setView(points[0], 12);
  }, [stations, map]);
  return null;
}

function severityOf(station) {
  const value = Number(station.pm25_mean);
  if (!Number.isFinite(value)) return { label: "Unclassified", color: "#8b91a8", score: null };
  if (value >= 60) return { label: "Critical", color: "#ff426d", score: value };
  if (value >= 40) return { label: "High", color: "#ff8b43", score: value };
  if (value >= 25) return { label: "Moderate", color: "#f6cf4a", score: value };
  return { label: "Low", color: "#38c994", score: value };
}

function Stat({ label, value, note, accent }) {
  return <article className="hm-stat">
    <div className="hm-stat-label">{label}</div>
    <strong style={{ color: accent || "#f4f5ff" }}>{value}</strong>
    <small>{note}</small>
  </article>;
}

function Donut({ values }) {
  const total = values.reduce((a, b) => a + b.count, 0) || 1;
  let cursor = 0;
  const colors = ["#35c98d", "#f4ce48", "#ff963e", "#ff426d"];
  const stops = values.map((v, i) => {
    const start = cursor / total * 100;
    cursor += v.count;
    return `${colors[i]} ${start}% ${cursor / total * 100}%`;
  }).join(", ");
  return <div className="hm-donut-wrap">
    <div className="hm-donut" style={{ background: `conic-gradient(${stops || "#34344f 0 100%"})` }}>
      <div><b>{total}</b><span>stations</span></div>
    </div>
  </div>;
}

export default function Hotspots() {
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);
  const [updatedAt, setUpdatedAt] = useState("");

  const loadStations = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(API_URL, { headers: { Accept: "application/json" } });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || `Hotspot API returned HTTP ${response.status}`);
      }
      const result = await response.json();
      if (!Array.isArray(result.hotspots)) throw new Error("API response does not contain a hotspots array.");
      setStations(result.hotspots);
      setUpdatedAt(new Date().toLocaleString());
    } catch (err) {
      setError(`${err.message}. Check FastAPI at ${API_BASE}.`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStations();
    const timer = window.setInterval(loadStations, 5 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [loadStations]);

  const validStations = useMemo(() => stations.filter(s =>
    Number.isFinite(Number(s.latitude)) && Number.isFinite(Number(s.longitude)) &&
    Number(s.latitude) >= -90 && Number(s.latitude) <= 90 &&
    Number(s.longitude) >= -180 && Number(s.longitude) <= 180
  ), [stations]);

  const filtered = useMemo(() => validStations.filter(s =>
    String(s.station_name || "").toLowerCase().includes(search.toLowerCase().trim())
  ), [validStations, search]);

  const distribution = useMemo(() => {
    const buckets = [
      { label: "Low", count: 0 }, { label: "Moderate", count: 0 },
      { label: "High", count: 0 }, { label: "Critical", count: 0 }
    ];
    validStations.forEach(s => {
      const level = severityOf(s).label;
      const item = buckets.find(b => b.label === level);
      if (item) item.count += 1;
    });
    return buckets;
  }, [validStations]);

  const meanPm = validStations.length
    ? validStations.reduce((sum, s) => sum + (Number(s.pm25_mean) || 0), 0) / validStations.length
    : null;
  const criticalCount = distribution[3].count + distribution[2].count;
  const format = value => Number.isFinite(Number(value)) ? Number(value).toFixed(1) : "—";

  return (
    <main className="hotspot-intel">
      <style>{`
        .hotspot-intel{--hm-bg:#101027;--hm-panel:#1c1b3d;--hm-panel2:#24234b;--hm-line:#39365f;--hm-muted:#a7a6c2;--hm-text:#f5f4ff;color:var(--hm-text);padding:clamp(14px,2vw,26px);display:grid;gap:15px;min-width:0;background:#101027}
        .hm-top{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
        .hm-brand{display:flex;align-items:center;gap:11px}.hm-brand-mark{width:38px;height:38px;border-radius:12px;background:linear-gradient(145deg,#ed32cc,#7256ff);display:grid;place-items:center;font-weight:900;font-size:19px;box-shadow:0 5px 22px #b82bba55}
        .hm-kicker{font-size:10px;letter-spacing:.17em;color:#b9a8ff;font-weight:800}.hm-title{font-size:clamp(21px,2.4vw,30px);margin:3px 0 0;font-weight:750;letter-spacing:-.04em}.hm-subtitle{color:var(--hm-muted);font-size:12px;margin:5px 0 0}
        .hm-actions{display:flex;align-items:center;gap:10px}.hm-live{display:flex;align-items:center;gap:7px;color:#70e2b0;font-size:11px;font-weight:700}.hm-dot{width:7px;height:7px;border-radius:50%;background:#48d99b;box-shadow:0 0 12px #48d99b}
        .hm-refresh{border:1px solid #514b7d;background:#29274d;color:#fff;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}.hm-refresh:disabled{opacity:.6;cursor:wait}
        .hm-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));background:linear-gradient(110deg,#211f43,#17172f);border:1px solid var(--hm-line);border-radius:15px;overflow:hidden}
        .hm-stat{padding:15px 18px;border-right:1px solid #39365f;display:grid;gap:5px;min-width:0}.hm-stat:last-child{border:0}.hm-stat-label{color:#b2b0cb;font-size:10px;text-transform:uppercase;letter-spacing:.09em}.hm-stat strong{font-size:25px;line-height:1.1}.hm-stat small{font-size:10px;color:#8f8eae}
        .hm-main-grid{display:grid;grid-template-columns:minmax(0,1.9fr) minmax(270px,.9fr);gap:12px;align-items:stretch}
        .hm-map-card,.hm-side-card,.hm-bottom-card{background:var(--hm-panel);border:1px solid var(--hm-line);border-radius:15px;overflow:hidden;min-width:0}
        .hm-card-head{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid #38365d}.hm-card-head h2{font-size:14px;margin:0}.hm-card-head p{font-size:10px;color:var(--hm-muted);margin:4px 0 0}
        .hm-map-wrap{height:490px;position:relative;background:#d9e6d4}.hm-map{height:100%;width:100%;z-index:1}.hm-map-legend{position:absolute;z-index:500;left:14px;bottom:14px;background:#17162ddd;border:1px solid #ffffff25;border-radius:10px;padding:10px 12px;backdrop-filter:blur(10px);font-size:10px;display:grid;gap:7px}.hm-legend-row{display:flex;align-items:center;gap:7px;color:#e8e6fa}.hm-legend-dot{width:8px;height:8px;border-radius:50%}
        .hm-map-foot{position:absolute;z-index:500;right:12px;bottom:13px;background:#17162ddd;border-radius:8px;padding:7px 10px;color:#ddd;font-size:9px}
        .hm-side-stack{display:grid;grid-template-rows:1fr 1fr;gap:12px;min-height:0}.hm-side-card{padding:14px 15px}.hm-side-title{font-size:13px;font-weight:750;margin:0}.hm-side-desc{font-size:10px;color:var(--hm-muted);margin:4px 0 12px}
        .hm-history{display:flex;align-items:center;gap:12px}.hm-donut-wrap{flex:0 0 auto}.hm-donut{width:126px;height:126px;border-radius:50%;display:grid;place-items:center;position:relative}.hm-donut:before{content:"";position:absolute;inset:19px;background:#1c1b3d;border-radius:50%}.hm-donut>div{position:relative;display:grid;text-align:center}.hm-donut b{font-size:22px}.hm-donut span{font-size:9px;color:var(--hm-muted)}.hm-legend{display:grid;gap:7px;flex:1}.hm-legend-item{display:flex;align-items:center;justify-content:space-between;gap:7px;font-size:10px;color:#deddf1}.hm-legend-item span:first-child{display:flex;align-items:center;gap:6px}.hm-legend-swatch{width:7px;height:7px;border-radius:50%}
        .hm-neighborhoods{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px}.hm-neighborhood{background:#29274e;border:1px solid #403d68;border-radius:10px;padding:10px 7px;text-align:center}.hm-neighborhood strong{font-size:18px;display:block}.hm-neighborhood span{font-size:9px;color:#b4b2cd;display:block;margin-top:3px}.hm-neighborhood small{font-size:8px;color:#8c8aa9}
        .hm-bottom-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:12px}.hm-bar-list{display:grid;gap:11px;padding:4px 0}.hm-bar-row{display:grid;grid-template-columns:minmax(85px,1fr) 2fr 35px;gap:10px;align-items:center;font-size:10px}.hm-bar-track{height:7px;border-radius:9px;background:#343253;overflow:hidden}.hm-bar-fill{height:100%;border-radius:9px}.hm-insight{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center}.hm-insight-big{font-size:33px;font-weight:800}.hm-insight-label{font-size:10px;color:var(--hm-muted)}.hm-pill{font-size:9px;padding:5px 8px;border-radius:99px;background:#2e2b5a;color:#c6bdff;display:inline-block}
        .hm-table-tools{display:flex;gap:8px;align-items:center}.hm-search{background:#17172f;border:1px solid #46436c;border-radius:8px;padding:8px 10px;color:#fff;min-width:170px;outline:none}.hm-table-wrap{overflow:auto}.hm-table{border-collapse:collapse;width:100%;font-size:11px;text-align:left}.hm-table th{padding:11px 14px;color:#a9a7c4;font-size:9px;text-transform:uppercase;letter-spacing:.08em;white-space:nowrap}.hm-table td{padding:12px 14px;border-top:1px solid #343253;white-space:nowrap}.hm-level{display:inline-flex;align-items:center;gap:6px;border-radius:99px;padding:5px 8px;background:#ffffff0c}.hm-level i{width:6px;height:6px;border-radius:50%}.hm-select{border:1px solid #4d4976;border-radius:7px;padding:5px 9px;color:#fff;background:#29274e;cursor:pointer}.hm-alert{padding:11px 13px;border-radius:10px;background:#69283d55;border:1px solid #d84c7044;color:#ffd3dc;font-size:11px}.hm-note{font-size:9px;color:#8e8ca9;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}
        @media(max-width:950px){.hm-main-grid{grid-template-columns:1fr}.hm-side-stack{grid-template-columns:1fr 1fr;grid-template-rows:auto}.hm-map-wrap{height:430px}}
        @media(max-width:650px){.hm-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.hm-stat:nth-child(2){border-right:0}.hm-stat:nth-child(-n+2){border-bottom:1px solid #39365f}.hm-side-stack,.hm-bottom-grid{grid-template-columns:1fr}.hm-map-wrap{height:390px}.hm-history{justify-content:space-around}.hm-title{font-size:22px}.hm-stat{padding:12px}.hm-stat strong{font-size:21px}.hm-search{min-width:0;width:100%}.hm-table-tools{width:100%}.hm-card-head{align-items:flex-start;flex-wrap:wrap}}
      `}</style>

      <header className="hm-top">
        <div className="hm-brand">
          <div className="hm-brand-mark">O</div>
          <div><div className="hm-kicker">ORIVA / SPATIAL INTELLIGENCE</div><h1 className="hm-title">Pollution Hotspot Intelligence</h1><p className="hm-subtitle">Pune, Maharashtra · Geographic pollution monitoring & DBSCAN cluster analysis</p></div>
        </div>
        <div className="hm-actions"><span className="hm-live"><i className="hm-dot" /> DATA CONNECTED</span><button className="hm-refresh" onClick={loadStations} disabled={loading}>{loading ? "Updating…" : "↻ Refresh data"}</button></div>
      </header>

      <section className="hm-stats">
        <Stat label="Monitoring stations" value={stations.length || "—"} note="CPCB dataset records" />
        <Stat label="Average PM2.5" value={meanPm === null ? "—" : format(meanPm)} note="µg/m³ · historical mean" accent="#f6d34f" />
        <Stat label="Mapped locations" value={validStations.length || "—"} note="Valid geographic coordinates" accent="#62d9bc" />
        <Stat label="High / critical zones" value={criticalCount} note="Based on historical PM2.5 mean" accent="#ff7a65" />
      </section>

      {error && <div className="hm-alert" role="alert">{error}</div>}

      <section className="hm-main-grid">
        <article className="hm-map-card">
          <div className="hm-card-head"><div><h2>Live spatial view · Pune region</h2><p>Historical station clusters with severity halos · Select a marker for details</p></div><span className="hm-pill">{filtered.length} mapped stations</span></div>
          <div className="hm-map-wrap">
            {loading && stations.length === 0 ? <div style={{padding:30,color:"#24234b"}}>Loading geospatial records…</div> :
              validStations.length === 0 ? <div style={{padding:30,color:"#24234b"}}>No station coordinates returned by the hotspot API.</div> :
              <MapContainer className="hm-map" center={PUNE_CENTER} zoom={11} scrollWheelZoom>
                <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                <FitStations stations={filtered} />
                {filtered.map((station, index) => {
                  const level = severityOf(station);
                  const position = [Number(station.latitude), Number(station.longitude)];
                  const radius = level.score === null ? 450 : Math.max(280, Math.min(1100, level.score * 12));
                  return <span key={`${station.station_name}-halo-${index}`}>
                    <Circle center={position} radius={radius * 2.1} pathOptions={{color:level.color,weight:0,fillColor:level.color,fillOpacity:.10}} />
                    <Circle center={position} radius={radius} pathOptions={{color:level.color,weight:0,fillColor:level.color,fillOpacity:.20}} />
                    <CircleMarker center={position} radius={selected?.station_name === station.station_name ? 11 : 7} pathOptions={{color:"#fff",weight:2,fillColor:level.color,fillOpacity:1}} eventHandlers={{click:()=>setSelected(station)}}>
                      <Popup><div style={{minWidth:170}}><b>{station.station_name || "Pune station"}</b><p>Mean PM2.5: {format(station.pm25_mean)} µg/m³</p><p>Maximum PM2.5: {format(station.pm25_max)} µg/m³</p><p>DBSCAN cluster: {station.cluster ?? "—"}</p><b style={{color:level.color}}>{level.label} historical level</b><p style={{fontSize:10}}>Historical dataset; not a live reading.</p></div></Popup>
                    </CircleMarker>
                  </span>;
                })}
              </MapContainer>}
            <div className="hm-map-legend">
              {["Critical","High","Moderate","Low"].map(label => <div className="hm-legend-row" key={label}><i className="hm-legend-dot" style={{background:severityOf({pm25_mean:label==="Critical"?70:label==="High"?48:label==="Moderate"?30:10}).color}} />{label}</div>)}
            </div>
            <div className="hm-map-foot">PUNE · INDIA · OpenStreetMap</div>
          </div>
        </article>

        <div className="hm-side-stack">
          <article className="hm-side-card">
            <h2 className="hm-side-title">Air quality distribution</h2><p className="hm-side-desc">Historical station breakdown by PM2.5 mean</p>
            <div className="hm-history"><Donut values={distribution} /><div className="hm-legend">{distribution.map((item,i)=><div className="hm-legend-item" key={item.label}><span><i className="hm-legend-swatch" style={{background:["#35c98d","#f4ce48","#ff963e","#ff426d"][i]}} />{item.label}</span><b>{validStations.length ? Math.round(item.count/validStations.length*100) : 0}%</b></div>)}</div></div>
            <p className="hm-side-desc" style={{marginTop:10}}>Based on available historical station means, not official real-time AQI categories.</p>
          </article>
          <article className="hm-side-card">
            <h2 className="hm-side-title">Neighborhood comparison</h2><p className="hm-side-desc">Highest PM2.5 monitoring stations in the dataset</p>
            <div className="hm-neighborhoods">{[...validStations].sort((a,b)=>(Number(b.pm25_mean)||0)-(Number(a.pm25_mean)||0)).slice(0,3).map((s,i)=><div className="hm-neighborhood" key={s.station_name || i}><strong style={{color:severityOf(s).color}}>{format(s.pm25_mean)}</strong><span>{s.station_name || `Station ${i+1}`}</span><small>µg/m³ mean</small></div>)}</div>
          </article>
        </div>
      </section>

      <section className="hm-bottom-grid">
        <article className="hm-bottom-card" style={{padding:15}}>
          <div className="hm-card-head" style={{padding:"0 0 13px",border:0}}><div><h2>Station concentration insights</h2><p>Top 6 stations by historical PM2.5 mean</p></div></div>
          <div className="hm-bar-list">{[...validStations].sort((a,b)=>(Number(b.pm25_mean)||0)-(Number(a.pm25_mean)||0)).slice(0,6).map((s,i)=>{const val=Number(s.pm25_mean)||0;const max=Math.max(1,...validStations.map(x=>Number(x.pm25_mean)||0));return <div className="hm-bar-row" key={s.station_name || i}><span title={s.station_name}>{s.station_name || `Station ${i+1}`}</span><div className="hm-bar-track"><div className="hm-bar-fill" style={{width:`${val/max*100}%`,background:severityOf(s).color}} /></div><b>{format(val)}</b></div>})}</div>
        </article>
        <article className="hm-bottom-card" style={{padding:15}}>
          <h2 className="hm-side-title">Address insights</h2><p className="hm-side-desc">Coverage and cluster intelligence</p>
          <div className="hm-insight"><div><div className="hm-insight-big">{validStations.length ? Math.round(validStations.length/stations.length*100) : 0}%</div><div className="hm-insight-label">Coordinate coverage</div><span className="hm-pill" style={{marginTop:10}}>Geospatial readiness</span></div><div style={{textAlign:"right"}}><div className="hm-insight-big" style={{fontSize:26}}>{new Set(validStations.map(s=>String(s.cluster))).size || 0}</div><div className="hm-insight-label">DBSCAN labels</div></div></div>
          <div style={{height:1,background:"#39365f",margin:"17px 0"}} />
          <div className="hm-legend-item"><span>Noise points (cluster -1)</span><b>{validStations.filter(s=>Number(s.cluster)===-1).length}</b></div>
          <div className="hm-legend-item" style={{marginTop:10}}><span>Cluster members</span><b>{validStations.filter(s=>Number(s.cluster)!==-1).length}</b></div>
          <p className="hm-side-desc" style={{marginTop:14}}>Cluster labels describe spatial grouping; severity colors are derived from historical PM2.5 means.</p>
        </article>
      </section>

      <section className="hm-bottom-card">
        <div className="hm-card-head"><div><h2>Station explorer</h2><p>Search, inspect and select a mapped monitoring station</p></div><div className="hm-table-tools"><input className="hm-search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search station…" aria-label="Search stations" /></div></div>
        <div className="hm-table-wrap"><table className="hm-table"><thead><tr><th>Station</th><th>Mean PM2.5</th><th>Max PM2.5</th><th>DBSCAN cluster</th><th>Historical level</th><th>Action</th></tr></thead><tbody>
          {filtered.map((s,i)=>{const level=severityOf(s);return <tr key={s.station_name || i}><td>{s.station_name || "Unnamed station"}</td><td>{format(s.pm25_mean)} µg/m³</td><td>{format(s.pm25_max)} µg/m³</td><td>{s.cluster ?? "—"}</td><td><span className="hm-level"><i style={{background:level.color}} />{level.label}</span></td><td><button className="hm-select" onClick={()=>setSelected(s)}>View on map</button></td></tr>})}
        </tbody></table>{!loading && filtered.length===0 && <div style={{padding:18,color:"#aaa9c4",fontSize:11}}>No matching station records.</div>}</div>
        {selected && <div style={{padding:"12px 15px",borderTop:"1px solid #39365f",fontSize:11,color:"#c9c7e0"}}><b>Selected: {selected.station_name}</b> · {selected.latitude}, {selected.longitude} · Mean PM2.5: {format(selected.pm25_mean)} µg/m³ · DBSCAN cluster: {selected.cluster ?? "—"}</div>}
      </section>

      <footer className="hm-note"><span>Source: data/processed/pune_cpcb_features.csv · Historical DBSCAN output</span><span>Last API response: {updatedAt || "Waiting for data"} · Auto-refresh: 5 min</span></footer>
    </main>
  );
}
