import { useCallback, useEffect, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  useMap
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

const API_URL = "http://127.0.0.1:8000/api/hotspots/";

function FitStations({ stations }) {
  const map = useMap();

  useEffect(() => {
    const points = stations
      .filter(s => Number.isFinite(Number(s.latitude)) &&
                   Number.isFinite(Number(s.longitude)))
      .map(s => [Number(s.latitude), Number(s.longitude)]);

    if (points.length === 1) {
      map.setView(points[0], 13);
    } else if (points.length > 1) {
      map.fitBounds(points, { padding: [35, 35], maxZoom: 13 });
    }
  }, [stations, map]);

  return null;
}

function Metric({ label, value }) {
  return (
    <div style={styles.metric}>
      <span style={styles.muted}>{label}</span>
      <strong>{value}</strong>
    </div>
  );
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
      const response = await fetch(API_URL);
      if (!response.ok) {
        throw new Error(`Hotspot API returned HTTP ${response.status}`);
      }

      const result = await response.json();
      if (!Array.isArray(result.hotspots)) {
        throw new Error("API response does not contain a hotspots array.");
      }

      setStations(result.hotspots);
      setUpdatedAt(new Date().toLocaleTimeString());
    } catch (err) {
      setError(
        `${err.message}. Confirm that FastAPI is running at http://127.0.0.1:8000.`
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStations();
  }, [loadStations]);

  const validStations = stations.filter(s =>
    Number.isFinite(Number(s.latitude)) &&
    Number.isFinite(Number(s.longitude)) &&
    Number(s.latitude) >= -90 &&
    Number(s.latitude) <= 90 &&
    Number(s.longitude) >= -180 &&
    Number(s.longitude) <= 180
  );

  const filtered = validStations.filter(s =>
    String(s.station_name || "")
      .toLowerCase()
      .includes(search.toLowerCase().trim())
  );

  const formatNumber = value =>
    Number.isFinite(Number(value)) ? Number(value).toFixed(2) : "N/A";

  return (
    <main style={styles.page}>
      <header style={styles.header}>
        <div>
          <div style={styles.eyebrow}>ORIVA / SPATIAL INTELLIGENCE</div>
          <h1 style={styles.title}>Pollution Hotspot Map</h1>
          <p style={styles.muted}>
            Explore station locations and historical DBSCAN analysis.
          </p>
        </div>
        <button
          style={styles.button}
          onClick={loadStations}
          disabled={loading}
        >
          {loading ? "Loading…" : "↻ Refresh data"}
        </button>
      </header>

      <div style={styles.warning}>
        <strong>Historical data — not live readings.</strong>
        <span>
          The API describes historical station clusters from the processed
          Pune CPCB dataset. Refreshing reloads this dataset; it does not make
          the measurements live.
        </span>
      </div>

      <section style={styles.metrics}>
        <Metric label="Stations returned" value={stations.length} />
        <Metric label="Stations with coordinates" value={validStations.length} />
        <Metric label="DBSCAN noise stations" value={
          validStations.filter(s => Number(s.cluster) === -1).length
        } />
      </section>

      {error && (
        <div role="alert" style={styles.error}>
          {error}
        </div>
      )}

      <section style={styles.mapPanel}>
        <div style={styles.panelHeading}>
          <div>
            <h2 style={styles.heading}>Pune monitoring stations</h2>
            <p style={styles.muted}>
              Select a marker to inspect historical statistics.
            </p>
          </div>
          <span style={styles.count}>{filtered.length} mapped</span>
        </div>

        {loading && stations.length === 0 ? (
          <div style={styles.empty}>Loading station data…</div>
        ) : validStations.length === 0 ? (
          <div style={styles.empty}>
            {error ? "Map data could not be loaded." : "No valid station coordinates were returned."}
          </div>
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

            {filtered.map((station, index) => {
              const noise = Number(station.cluster) === -1;
              return (
                <CircleMarker
                  key={`${station.station_name}-${index}`}
                  center={[
                    Number(station.latitude),
                    Number(station.longitude)
                  ]}
                  radius={selected?.station_name === station.station_name ? 12 : 9}
                  pathOptions={{
                    color: noise ? "#f59e0b" : "#14b8a6",
                    fillColor: noise ? "#f59e0b" : "#14b8a6",
                    fillOpacity: 0.85,
                    weight: 2
                  }}
                  eventHandlers={{
                    click: () => setSelected(station)
                  }}
                >
                  <Popup>
                    <strong>{station.station_name}</strong>
                    <p>Historical mean PM2.5: {formatNumber(station.pm25_mean)} µg/m³</p>
                    <p>Historical max PM2.5: {formatNumber(station.pm25_max)} µg/m³</p>
                    <p>DBSCAN cluster: {station.cluster}</p>
                    <p>Classification: {noise ? "Noise (-1)" : "Cluster member"}</p>
                    <small>Historical data; not a live reading.</small>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        )}
      </section>

      <section style={styles.tablePanel}>
        <div style={styles.panelHeading}>
          <h2 style={styles.heading}>Station explorer</h2>
          <input
            aria-label="Search stations"
            placeholder="Search station…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={styles.search}
          />
        </div>

        <div style={styles.tableScroll}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Station</th>
                <th style={styles.th}>Mean PM2.5</th>
                <th style={styles.th}>Maximum PM2.5</th>
                <th style={styles.th}>Cluster</th>
                <th style={styles.th}>Level</th>
                <th style={styles.th}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s, i) => (
                <tr key={`${s.station_name}-${i}`}>
                  <td style={styles.td}>{s.station_name}</td>
                  <td style={styles.td}>{formatNumber(s.pm25_mean)}</td>
                  <td style={styles.td}>{formatNumber(s.pm25_max)}</td>
                  <td style={styles.td}>{s.cluster}</td>
                  <td style={styles.td}>{s.pollution_level || "N/A"}</td>
                  <td style={styles.td}>
                    <button
                      style={styles.smallButton}
                      onClick={() => {
                        setSelected(s);
                        window.dispatchEvent(
                          new CustomEvent("oriva-map-select", { detail: s })
                        );
                      }}
                    >
                      Select
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && filtered.length === 0 && (
            <p style={styles.empty}>No matching stations.</p>
          )}
        </div>
        {selected && (
          <div style={styles.selected}>
            <strong>Selected: {selected.station_name}</strong>
            <span>
              Coordinates: {selected.latitude}, {selected.longitude}
              {" · "}Mean PM2.5: {formatNumber(selected.pm25_mean)} µg/m³
              {" · "}Cluster: {selected.cluster}
            </span>
          </div>
        )}
      </section>

      <footer style={styles.footer}>
        Source: data/processed/pune_cpcb_features.csv · API refresh time: {updatedAt || "Not loaded"}
      </footer>
    </main>
  );
}

const styles = {
  page: {
    color: "var(--text, #e8eef7)",
    padding: "clamp(16px, 3vw, 30px)",
    display: "grid",
    gap: 20,
    minWidth: 0
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 16,
    flexWrap: "wrap"
  },
  eyebrow: {
    color: "#54d6b0",
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "0.15em"
  },
  title: { fontSize: "clamp(25px, 3vw, 36px)", margin: "8px 0" },
  muted: { color: "var(--muted, #9aa9bd)", fontSize: 13, margin: "5px 0" },
  button: {
    border: 0, borderRadius: 10, padding: "11px 16px",
    color: "#05271f", background: "#54d6b0",
    cursor: "pointer", fontWeight: 800
  },
  warning: {
    display: "grid", gap: 5, padding: 15, borderRadius: 12,
    background: "rgba(245,158,11,.10)",
    border: "1px solid rgba(245,158,11,.4)",
    color: "var(--text, #e8eef7)", fontSize: 13
  },
  metrics: {
    display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: 12
  },
  metric: {
    display: "grid", gap: 9, padding: 17, borderRadius: 13,
    border: "1px solid var(--border, #273448)",
    background: "var(--panel, #101a29)"
  },
  mapPanel: {
    overflow: "hidden", borderRadius: 16,
    border: "1px solid var(--border, #273448)",
    background: "var(--panel, #101a29)"
  },
  panelHeading: {
    display: "flex", justifyContent: "space-between",
    alignItems: "center", gap: 12, flexWrap: "wrap", padding: 17
  },
  heading: { fontSize: 17, margin: 0 },
  count: { color: "#54d6b0", fontSize: 12 },
  map: { height: 500, width: "100%", background: "#dce4e8", zIndex: 1 },
  empty: { padding: 28, textAlign: "center", color: "var(--muted, #9aa9bd)" },
  error: {
    padding: 14, borderRadius: 10, color: "#fecaca",
    background: "rgba(220,38,38,.12)", border: "1px solid #7f1d1d"
  },
  tablePanel: {
    borderRadius: 16, overflow: "hidden",
    border: "1px solid var(--border, #273448)",
    background: "var(--panel, #101a29)"
  },
  search: {
    padding: "10px 12px", minWidth: 190, maxWidth: "100%",
    color: "inherit", background: "var(--surface, #0b1320)",
    border: "1px solid var(--border, #273448)", borderRadius: 9
  },
  tableScroll: { overflowX: "auto" },
  table: { width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 13 },
  th: { padding: 12, whiteSpace: "nowrap", color: "#8fa2b9", borderBottom: "1px solid #273448" },
  td: { padding: 12, whiteSpace: "nowrap", borderBottom: "1px solid rgba(148,163,184,.12)" },
  smallButton: {
    padding: "6px 10px", borderRadius: 7, border: "1px solid #3b5268",
    color: "inherit", background: "transparent", cursor: "pointer"
  },
  selected: {
    padding: 15, display: "grid", gap: 6,
    color: "var(--muted, #9aa9bd)", fontSize: 13
  },
  footer: { color: "var(--muted, #9aa9bd)", fontSize: 11 }
};