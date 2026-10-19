import pytest
from fastapi import HTTPException

from backend.api.routes import hotspots


def test_hotspot_endpoint_returns_historical_cluster_response(monkeypatch):
    sample = [{
        "station_name": "Example",
        "cluster": 0,
        "is_hotspot_cluster": True,
        "is_pollution_hotspot": True,
    }]
    monkeypatch.setattr(hotspots, "get_hotspot_clusters", lambda: sample)

    response = hotspots.get_hotspots()

    assert response["status"] == "ok"
    assert response["count"] == 1
    assert response["hotspots"] == sample
    assert "not live pollution readings" in response["message"]


def test_hotspot_endpoint_reports_missing_detector(monkeypatch):
    monkeypatch.setattr(hotspots, "get_hotspot_clusters", None)

    with pytest.raises(HTTPException) as exc:
        hotspots.get_hotspots()

    assert exc.value.status_code == 503


def test_hotspot_endpoint_reports_missing_input(monkeypatch):
    def missing_input():
        raise FileNotFoundError("feature file missing")

    monkeypatch.setattr(hotspots, "get_hotspot_clusters", missing_input)

    with pytest.raises(HTTPException) as exc:
        hotspots.get_hotspots()

    assert exc.value.status_code == 503
