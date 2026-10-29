import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const API_URL = `${API_BASE}/api/hotspots/`;

const COLORS = {
  hotspot: "#f43f5e",
  high: "#f97316",
  elevated: "#eab308",
  cluster: "#14b8a6",
  noise: "#94a3b8"
};

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function formatNumber(value) {
  const n = numberOrNull(value);
  return n === null ? "N/A" : n.toFixed(2);
}

function isHotspot(station) {
  return [true, 1, "true"].includes(station.is_pollution_hotspot);
}

function getClassification(station) {
  const mean = numberOrNull(station.pm25_mean);
  if (isHotspot(station)) {
    return { key: "hotspot", label: "Pollution hotspot", color: COLORS.hotspot };
  }
  if (mean !== null && mean >= 60) {
    return { key: "high", label: "High historical mean PM2.5", color: COLORS.high };
  }
  if (mean !== null && mean >= 35) {
    return { key: "elevated", label: "Elevated historical mean PM2.5", color: COLORS.elevated };
  }
  if (numberOrNull(station.cluster) === -1) {
    return { key: "noise", label: "DBSCAN noise station", color: COLORS.noise };
  }
  return { key: "cluster", label: "Spatial cluster member", color: COLORS.cluster };
}

function FitStations({ stations }) {
  const map = useMap();

  useEffect(() => {
    const points = stations.map(s => [Number(s.latitude), Number(s.longitude)]);
    if (points.length === 1) map.setView(points[0], 13);
    else if (points.length > 1) map.fitBounds(points, { padding: [35, 35], maxZoom: 13 });
  }, [stations, map]);

  return null;
}

function FlyToSelected({ station }) {
  const map = useMap();

  useEffect(() => {
    if (!station) return;
    const lat = numberOrNull(station.latitude);
    const lon = numberOrNull(station.longitude);
    if (lat !== null && lon !== null) map.flyTo([lat, lon], 14, { duration: 0.6 });
  }, [station, map]);

  return null;
}

function Metric({ label, value, detail }) {
  return (
    <div style={styles.metric}>
      <span style={styles.muted}>{label}</span>
      <strong style={styles.metricValue}>{value}</strong>
      {detail && <span style={styles.metricDetail}>{detail}</span>}
    </div>
  );
}

export default function Hotspots() {
  const [stations, setStations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(null);
  const [updatedAt, setUpdatedAt] = useState("");
  const [apiMessage, setApiMessage] = useState("");

  const loadStations = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(API_URL);
      if (!response.ok) {
        let detail = "";
        try {
          const body = await response.json();
          detail = body.detail ? `: ${body.detail}` : "";
        } catch {
          // Keep the HTTP status as the useful error.
        }
        throw new Error(`Hotspot API returned HTTP ${response.status}${detail}`);
      }

      const result = await response.json();
      if (!Array.isArray(result.hotspots)) {
        throw new Error("API response does not contain a hotspots array.");
      }

      const valid = result.hotspots.filter(s => {
        const lat = numberOrNull(s.latitude);
        const lon = numberOrNull(s.longitude);
        return lat !== null && lon !== null &&
          lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
      });

      setStations(valid);
      setApiMessage(result.message || "Historical station-cluster data.");
      setUpdatedAt(new Date().toLocaleString());

      setSelected(current => {
        if (!current) return null;
        return valid.find(s => s.station_name === current.station_name) || null;
      });
    } catch (err) {
      setError(`${err.message}. Check that FastAPI is running at ${API_BASE}.`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStations();
  }, [loadStations]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();

    return stations.filter(station => {
      const matchesSearch = String(station.station_name || "")
        .toLowerCase().includes(query);
      const category = getClassification(station).key;
      const matchesFilter = filter === "all" || category === filter;
      return matchesSearch && matchesFilter;
    });
  }, [stations, search, filter]);

  const countBy = key => stations.filter(s => getClassification(s).key === key).length;
  const selectStation = station => setSelected(station);

  return (
    <main style={styles.page}>
      <header style={styles.header}>
        <div>
          <div style={styles.eyebrow}>ORIVA / SPATIAL INTELLIGENCE</div>
          <h1 style={styles.title}>Interactive Pollution Map</h1>
          <p style={styles.muted}>
            Explore Pune monitoring stations, historical PM2.5 statistics and DBSCAN classifications.
          </p>
        </div>
        <button style={styles.button} onClick={loadStations} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh data"}
        </button>
      </header>

      <div style={styles.warning}>
        <strong>Historical analysis - not live readings</strong>
        <span>
          {apiMessage || "Station statistics and clusters are derived from the processed Pune dataset."}
          {" "}Refreshing reloads the API data; it does not make historical measurements live.
        </span>
      </div>

      <section style={styles.metrics}>
        <Metric label="Mapped stations" value={stations.length} />
        <Metric label="Pollution hotspots" value={countBy("hotspot")} detail="Flagged by backend" />
        <Metric label="High mean PM2.5" value={countBy("high")} detail="At least 60 µg/m³" />
        <Metric label="Elevated mean PM2.5" value={countBy("elevated")} detail="35 to below 60 µg/m³" />
        <Metric label="Spatial cluster members" value={countBy("cluster")} />
        <Metric label="DBSCAN noise stations" value={countBy("noise")} />
      </section>

      {error && <div role="alert" style={styles.error}>{error}</div>}

      <section style={styles.panel}>
        <div style={styles.panelHeading}>
          <div>
            <h2 style={styles.heading}>Pune station map</h2>
            <p style={styles.muted}>Zoom, pan, select markers, or select a station from the table.</p>
          </div>
          <span style={styles.count}>{filtered.length} stations shown</span>
        </div>

        <div style={styles.toolbar}>
          <input
            aria-label="Search station names"
            placeholder="Search station..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={styles.input}
          />
          <select
            aria-label="Filter station classification"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            style={styles.input}
          >
            <option value="all">All classifications</option>
            <option value="hotspot">Pollution hotspots</option>
            <option value="high">High mean PM2.5</option>
            <option value="elevated">Elevated mean PM2.5</option>
            <option value="cluster">Spatial cluster members</option>
            <option value="noise">DBSCAN noise stations</option>
          </select>
          <button
            style={styles.secondaryButton}
            onClick={() => { setSearch(""); setFilter("all"); setSelected(null); }}
          >
            Reset filters
          </button>
        </div>

        <div style={styles.legend} aria-label="Map legend">
          {[
            ["hotspot", "Pollution hotspot"],
            ["high", "Mean PM2.5 >= 60"],
            ["elevated", "Mean PM2.5 >= 35"],
            ["cluster", "Spatial cluster member"],
            ["noise", "DBSCAN noise"]
          ].map(([key, label]) => (
            <span key={key} style={styles.legendItem}>
              <span style={{ ...styles.legendDot, background: COLORS[key] }} />
              {label}
            </span>
          ))}
          <span style={styles.metricDetail}>
            PM2.5 thresholds use historical mean concentrations, not live AQI.
          </span>
        </div>

        {loading && stations.length === 0 ? (
          <div style={styles.empty}>Loading station data...</div>
        ) : stations.length === 0 ? (
          <div style={styles.empty}>No station data is available. Check the backend and processed dataset.</div>
        ) : filtered.length === 0 ? (
          <div style={styles.empty}>No stations match the current search and filter.</div>
        ) : (
          <MapContainer
            center={[18.52, 73.86]}
            zoom={11}
            scrollWheelZoom
            style={styles.map}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <FitStations stations={filtered} />
            <FlyToSelected station={selected} />

            {filtered.map((station, index) => {
              const classification = getClassification(station);
              const isSelected = selected?.station_name === station.station_name;

              return (
                <CircleMarker
                  key={`${station.station_name}-${station.latitude}-${station.longitude}-${index}`}
                  center={[Number(station.latitude), Number(station.longitude)]}
                  radius={isSelected ? 12 : 8}
                  pathOptions={{
                    color: isSelected ? "#ffffff" : classification.color,
                    fillColor: classification.color,
                    fillOpacity: 0.88,
                    weight: isSelected ? 4 : 2
                  }}
                  eventHandlers={{ click: () => selectStation(station) }}
                >
                  <Popup>
                    <div style={{ minWidth: 190 }}>
                      <strong>{station.station_name || "Unnamed station"}</strong>
                      <p>Classification: {classification.label}</p>
                      <p>Historical mean PM2.5: {formatNumber(station.pm25_mean)} µg/m³</p>
                      <p>Historical maximum PM2.5: {formatNumber(station.pm25_max)} µg/m³</p>
                      <p>DBSCAN cluster: {station.cluster ?? "N/A"}</p>
                      <p>Observations: {station.observations ?? "N/A"}</p>
                      <p>Coordinates: {formatNumber(station.latitude)}, {formatNumber(station.longitude)}</p>
                      <small>Historical dataset; not a live reading.</small>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        )}
      </section>

      <section style={styles.panel}>
        <div style={styles.panelHeading}>
          <div>
            <h2 style={styles.heading}>Station explorer</h2>
            <p style={styles.muted}>Select a row to zoom to that station on the map.</p>
          </div>
          <span style={styles.count}>{filtered.length} results</span>
        </div>

        <div style={styles.tableScroll}>
          <table style={styles.table}>
            <thead>
              <tr>
                {["Station", "Mean PM2.5", "Maximum PM2.5", "Cluster", "Classification", "Action"].map(label =>
                  <th key={label} style={styles.th}>{label}</th>
                )}
              </tr>
            </thead>
            <tbody>
              {filtered.map((station, index) => {
                const classification = getClassification(station);
                const active = selected?.station_name === station.station_name;

                return (
                  <tr key={`${station.station_name}-${index}`}
                    style={active ? styles.activeRow : undefined}>
                    <td style={styles.td}>{station.station_name || "Unnamed station"}</td>
                    <td style={styles.td}>{formatNumber(station.pm25_mean)}</td>
                    <td style={styles.td}>{formatNumber(station.pm25_max)}</td>
                    <td style={styles.td}>{station.cluster ?? "N/A"}</td>
                    <td style={styles.td}>
                      <span style={{ ...styles.pill, borderColor: classification.color, color: classification.color }}>
                        {classification.label}
                      </span>
                    </td>
                    <td style={styles.td}>
                      <button style={styles.secondaryButton} onClick={() => selectStation(station)}>
                        {active ? "Selected" : "Locate"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {selected && (
          <div style={styles.selected}>
            <strong>Selected station: {selected.station_name}</strong>
            <span>
              Mean PM2.5: {formatNumber(selected.pm25_mean)} µg/m³
              {" | "}Cluster: {selected.cluster ?? "N/A"}
              {" | "}Coordinates: {formatNumber(selected.latitude)}, {formatNumber(selected.longitude)}
            </span>
            <button style={styles.secondaryButton} onClick={() => setSelected(null)}>
              Clear selection
            </button>
          </div>
        )}
      </section>

      <footer style={styles.footer}>
        Source: historical Pune CPCB processed dataset via FastAPI {API_URL}
        {" | "}Last API refresh: {updatedAt || "Not loaded"}
      </footer>
    </main>
  );
}

const styles = {
  page: { color: "var(--text, #e8eef7)", padding: "clamp(16px, 3vw, 30px)", display: "grid", gap: 20, minWidth: 0 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" },
  eyebrow: { color: "#54d6b0", fontSize: 11, fontWeight: 800, letterSpacing: "0.15em" },
  title: { fontSize: "clamp(25px, 3vw, 36px)", margin: "8px 0" },
  muted: { color: "var(--muted, #9aa9bd)", fontSize: 13, margin: "5px 0" },
  button: { border: 0, borderRadius: 10, padding: "11px 16px", color: "#05271f", background: "#54d6b0", cursor: "pointer", fontWeight: 800 },
  secondaryButton: { border: "1px solid var(--border, #3b5268)", borderRadius: 8, padding: "8px 11px", color: "inherit", background: "transparent", cursor: "pointer", whiteSpace: "nowrap" },
  warning: { display: "grid", gap: 5, padding: 15, borderRadius: 12, background: "rgba(245,158,11,.10)", border: "1px solid rgba(245,158,11,.4)", fontSize: 13 },
  metrics: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(145px, 1fr))", gap: 12 },
  metric: { display: "grid", gap: 8, padding: 16, borderRadius: 13, border: "1px solid var(--border, #273448)", background: "var(--panel, #101a29)" },
  metricValue: { fontSize: 25 },
  metricDetail: { color: "var(--muted, #9aa9bd)", fontSize: 11, width: "100%" },
  panel: { overflow: "hidden", borderRadius: 16, border: "1px solid var(--border, #273448)", background: "var(--panel, #101a29)" },
  panelHeading: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", padding: 17 },
  heading: { fontSize: 17, margin: 0 },
  count: { color: "#54d6b0", fontSize: 12 },
  toolbar: { display: "flex", flexWrap: "wrap", gap: 10, padding: "0 17px 16px" },
  input: { minWidth: 180, maxWidth: "100%", padding: "10px 12px", color: "inherit", background: "var(--surface, #0b1320)", border: "1px solid var(--border, #273448)", borderRadius: 9 },
  legend: { display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12, padding: "0 17px 16px", fontSize: 12 },
  legendItem: { display: "inline-flex", alignItems: "center", gap: 6, color: "var(--muted, #9aa9bd)" },
  legendDot: { width: 10, height: 10, borderRadius: "50%", display: "inline-block", flexShrink: 0 },
  map: { height: "min(65vh, 620px)", minHeight: 380, width: "100%", background: "#dce4e8", zIndex: 1 },
  empty: { padding: 28, textAlign: "center", color: "var(--muted, #9aa9bd)" },
  error: { padding: 14, borderRadius: 10, color: "#fecaca", background: "rgba(220,38,38,.12)", border: "1px solid #7f1d1d", overflowWrap: "anywhere" },
  tableScroll: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 13 },
  th: { padding: 12, whiteSpace: "nowrap", color: "#8fa2b9", borderBottom: "1px solid #273448" },
  td: { padding: 12, borderBottom: "1px solid rgba(148,163,184,.12)", verticalAlign: "middle" },
  activeRow: { background: "rgba(84,214,176,.08)" },
  pill: { display: "inline-block", border: "1px solid", borderRadius: 20, padding: "4px 8px", fontSize: 11, whiteSpace: "nowrap" },
  selected: { padding: 15, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12, color: "var(--muted, #9aa9bd)", fontSize: 13 },
  footer: { color: "var(--muted, #9aa9bd)", fontSize: 11, overflowWrap: "anywhere" }
};