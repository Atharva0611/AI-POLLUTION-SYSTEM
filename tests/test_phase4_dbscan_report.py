from backend.agents import final_agent
from backend.ml.dbscan import hotspot_detection


def test_legacy_agent_uses_real_dbscan_and_real_cluster_metadata(monkeypatch):
    sample = [
        {
            "station_name": "Example A",
            "latitude": 18.52,
            "longitude": 73.85,
            "pm25_mean": 125.0,
            "pm25_max": 150.0,
            "observations": 10,
            "cluster": 0,
            "is_hotspot_cluster": True,
            "is_pollution_hotspot": True,
        },
        {
            "station_name": "Example B",
            "latitude": 18.521,
            "longitude": 73.851,
            "pm25_mean": 35.0,
            "pm25_max": 40.0,
            "observations": 8,
            "cluster": 0,
            "is_hotspot_cluster": True,
            "is_pollution_hotspot": False,
        },
    ]
    calls = []

    def fake_dbscan(*, eps_km, min_samples):
        calls.append((eps_km, min_samples))
        return sample

    monkeypatch.setattr(hotspot_detection, "get_hotspot_clusters", fake_dbscan)
    monkeypatch.setattr(
        final_agent, "_extract_location_from_question", lambda question: "Pune"
    )

    db = final_agent.dbscan_node({"question": "Pune hotspots"})["dbscan"]

    assert calls == [(5.0, 2)]
    assert len(db["stations"]) == 2
    assert db["hotspot_count"] == 1
    assert db["cluster_count"] == 1
    assert db["stations"][0]["category"] == "Critical Hotspot"
    assert db["stations"][1]["category"] == "Moderate / Lower"

    report = final_agent.final_node({"route": "dbscan", "dbscan": db})["final_answer"]
    assert "eps=5 km, min_samples=2" in report
    assert "eps=0.75" not in report
    assert "Processed-dataset mean PM2.5" in report
    assert "not confirmed live readings" in report


def test_legacy_agent_does_not_report_pune_data_for_other_locations(monkeypatch):
    monkeypatch.setattr(
        final_agent, "_extract_location_from_question", lambda question: "Wagholi"
    )

    db = final_agent.dbscan_node({"question": "Wagholi hotspots"})["dbscan"]

    assert db["available"] is False
    assert db["status"] == "UNSUPPORTED_HOTSPOT_COVERAGE"
    assert db["stations"] == []

    report = final_agent.final_node({"route": "dbscan", "dbscan": db})["final_answer"]
    assert "UNSUPPORTED_HOTSPOT_COVERAGE" in report
    assert "No Pune results are presented" in report
