import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const DEFAULT_COORDS = { latitude: 18.5204, longitude: 73.8567 };

function formatTime(value) {
  if (!value) return "Timestamp unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function Freshness({ item }) {
  const status = item?.freshness || "unknown";
  const labels = {
    fresh: "Fresh observation",
    delayed: "Delayed observation",
    stale: "Stale observation",
    missing_timestamp: "Timestamp missing",
    invalid_timestamp: "Invalid timestamp",
    future_timestamp: "Timestamp needs review",
  };
  return <span className={`aq-freshness aq-freshness--${status}`}>{labels[status] || "Freshness unknown"}</span>;
}

export default function LiveAirQuality() {
  const [stations, setStations] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState(null);
  const [loadingStations, setLoadingStations] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [lastChecked, setLastChecked] = useState("");

  const loadStations = useCallback(async () => {
    setLoadingStations(true);
    setError("");
    try {
      const params = new URLSearchParams({ ...DEFAULT_COORDS, radius_m: "15000", limit: "100" });
      const response = await fetch(`${API_BASE}/api/air-quality/locations?${params}`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Station request failed (HTTP ${response.status})`);
      }
      const payload = await response.json();
      setStations(Array.isArray(payload.stations) ? payload.stations : []);
      setLastChecked(new Date().toLocaleString());
    } catch (err) {
      setError(err.message || "Could not load OpenAQ locations.");
      setStations([]);
    } finally {
      setLoadingStations(false);
    }
  }, []);

  const loadStationDetail = useCallback(async (id) => {
    if (!id) { setDetail(null); return; }
    setLoadingDetail(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/air-quality/stations/${encodeURIComponent(id)}`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Measurement request failed (HTTP ${response.status})`);
      }
      setDetail(await response.json());
    } catch (err) {
      setDetail(null);
      setError(err.message || "Could not load station measurements.");
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  useEffect(() => { loadStations(); }, [loadStations]);
  useEffect(() => { loadStationDetail(selectedId); }, [selectedId, loadStationDetail]);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return stations;
    return stations.filter(s => `${s.name || ""} ${s.locality || ""} ${s.id || ""}`.toLowerCase().includes(term));
  }, [stations, query]);

  const measurements = detail?.measurements || [];
  const pollutantOrder = ["pm25", "pm10", "no2", "so2", "o3", "co"];
  const sortedMeasurements = [...measurements].sort((a, b) => pollutantOrder.indexOf(a.pollutant) - pollutantOrder.indexOf(b.pollutant));
  const freshCount = measurements.filter(m => m.is_fresh).length;

  return (
    <main className="aq-page">
      <header className="aq-page-header">
        <div>
          <div className="aq-eyebrow">MONITORING / THIRD-PARTY DATA</div>
          <h1>Live air-quality stations</h1>
          <p>Inspect OpenAQ station metadata, pollutant measurements, observation times, and freshness before using readings as current conditions.</p>
        </div>
        <button className="aq-button" onClick={loadStations} disabled={loadingStations}>
          {loadingStations ? "Checking…" : "Refresh stations"}
        </button>
      </header>

      <div className="aq-notice" role="note">
        <strong>Source note</strong>
        <span>OpenAQ is a third-party air-quality data platform. These readings are not automatically official CPCB AQI. Each pollutant is freshness-checked independently; stale values are not presented as live.</span>
      </div>

      {error && <div className="aq-error" role="alert">{error}</div>}

      <div className="aq-workspace">
        <section className="aq-station-panel">
          <div className="aq-panel-title">
            <div><h2>Stations near Pune</h2><p>{stations.length} locations returned by OpenAQ</p></div>
            <span className="aq-count">{stations.length}</span>
          </div>
          <label className="aq-search-label" htmlFor="aq-station-search">Search station</label>
          <input id="aq-station-search" className="aq-search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Bhosari, Hadapsar, station ID…" />
          {loadingStations ? <p className="aq-empty">Loading station directory…</p> : (
            <div className="aq-station-list">
              {filtered.map(station => (
                <button key={station.id} className={`aq-station-row ${String(selectedId) === String(station.id) ? "is-selected" : ""}`} onClick={() => setSelectedId(String(station.id))}>
                  <span className="aq-station-symbol" aria-hidden="true">●</span>
                  <span className="aq-station-name"><strong>{station.name || "Unnamed station"}</strong><small>ID {station.id}{station.locality ? ` · ${station.locality}` : ""}</small></span>
                  <span className={station.is_monitor ? "aq-monitor-yes" : "aq-monitor-unknown"}>{station.is_monitor ? "Monitor" : "Other"}</span>
                </button>
              ))}
              {!filtered.length && <p className="aq-empty">No stations match this search.</p>}
            </div>
          )}
          <p className="aq-footnote">Directory checked: {lastChecked || "not yet checked"}. A monitor flag does not guarantee fresh readings.</p>
        </section>

        <section className="aq-detail-panel">
          {!selectedId ? (
            <div className="aq-detail-empty"><span className="aq-empty-mark">↖</span><h2>Select a station</h2><p>Choose a station from the directory to inspect its latest reported pollutant measurements.</p></div>
          ) : loadingDetail ? (
            <p className="aq-empty">Loading station measurements…</p>
          ) : detail ? (
            <>
              <div className="aq-panel-title aq-detail-heading">
                <div><div className="aq-eyebrow">STATION DETAIL / OPENAQ</div><h2>{detail.station?.name || `Station ${selectedId}`}</h2><p>Location ID {detail.location_id} · Third-party measurements</p></div>
                <button className="aq-button aq-button-secondary" onClick={() => loadStationDetail(selectedId)}>Refresh readings</button>
              </div>
              <div className="aq-detail-summary">
                <div><span>Measurements</span><strong>{measurements.length}</strong></div>
                <div><span>Fresh (under 24h)</span><strong>{freshCount}</strong></div>
                <div><span>Station flag</span><strong>{detail.station?.is_monitor === true ? "Monitor" : detail.station?.is_monitor === false ? "Not flagged" : "Unknown"}</strong></div>
              </div>
              <div className="aq-table-wrap">
                <table className="aq-table">
                  <thead><tr><th>Pollutant</th><th>Latest value</th><th>Observed (local time)</th><th>Freshness</th></tr></thead>
                  <tbody>
                    {sortedMeasurements.map((item, index) => (
                      <tr key={item.sensor_id || `${item.pollutant}-${index}`}>
                        <td><strong>{item.pollutant.toUpperCase()}</strong><small>Sensor {item.sensor_id ?? "—"}</small></td>
                        <td>{item.value == null ? "—" : item.value} <span>{item.unit || ""}</span></td>
                        <td>{formatTime(item.observed_at_utc)}</td>
                        <td><Freshness item={item} />{item.age_hours != null && <small className="aq-age">{item.age_hours} hours old</small>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!sortedMeasurements.length && <p className="aq-empty">No supported pollutant measurements were returned for this station.</p>}
              </div>
              <div className="aq-provenance">
                <strong>Interpretation</strong>
                <p>{detail.note || "Verify each observation timestamp and unit before interpretation."} A stale or missing timestamp must not be used as a live reading.</p>
              </div>
            </>
          ) : <div className="aq-detail-empty"><h2>Measurements unavailable</h2><p>Try refreshing the station or selecting another location.</p></div>}
        </section>
      </div>
      <footer className="aq-page-footer">Provider: OpenAQ API v3 · Timestamps are displayed in your browser's local timezone · API keys remain on the backend.</footer>
    </main>
  );
}
