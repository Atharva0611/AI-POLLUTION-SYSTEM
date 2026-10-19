from datetime import datetime, timedelta, timezone

import pytest

from backend.services import station_registry


def make_station(timestamp):
    return {
        "station_id": "TEST001",
        "station_name": "Test Station, Pune",
        "clean_name": "Test Station",
        "city": "Pune",
        "state": "Maharashtra",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "pollutants_available": ["PM2.5", "PM10"],
        "total_observations": 100,
        "latest_timestamp": timestamp,
        "data_quality_score": 0.9,
        "is_active": True,
    }


def test_fresh_station_is_eligible(monkeypatch):
    now = datetime.now(timezone.utc)
    station = make_station((now - timedelta(hours=1)).isoformat())

    monkeypatch.setattr(
        station_registry, "get_station_registry", lambda: {"test": station}
    )

    result = station_registry.discover_cpcb_stations(
        18.5204, 73.8567, max_observation_age_hours=72
    )

    assert result["case"] == "CASE_A"
    assert result["primary_station"]["clean_name"] == "Test Station"


@pytest.mark.parametrize(
    "timestamp",
    [
        (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        None,
        "not-a-valid-timestamp",
    ],
)
def test_stale_or_invalid_station_is_rejected(monkeypatch, timestamp):
    station = make_station(timestamp)

    monkeypatch.setattr(
        station_registry, "get_station_registry", lambda: {"test": station}
    )

    result = station_registry.discover_cpcb_stations(
        18.5204, 73.8567, max_observation_age_hours=72
    )

    assert result["case"] == "CASE_C"
    assert result["case_description"] == "STALE_OBSERVATIONS"
    assert result["primary_station"] is None
    assert result["eligible_stations"] == []
    assert "No CPCB station has an observation within 72 hours" in result["message"]
