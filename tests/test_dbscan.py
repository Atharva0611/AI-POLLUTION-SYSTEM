import pandas as pd
import pytest

from backend.ml.dbscan import hotspot_detection as hd


@pytest.fixture
def sample_stations():
    # Three nearby stations form a cluster; the fourth is spatially isolated.
    return pd.DataFrame([
        {"station_name": "A", "latitude": 18.5200, "longitude": 73.8500, "pm25": 70},
        {"station_name": "B", "latitude": 18.5210, "longitude": 73.8510, "pm25": 30},
        {"station_name": "C", "latitude": 18.5220, "longitude": 73.8520, "pm25": 65},
        {"station_name": "D", "latitude": 19.0000, "longitude": 74.0000, "pm25": 100},
    ])


def test_spatial_cluster_and_pollution_hotspot_are_distinct(
    sample_stations, tmp_path, monkeypatch
):
    monkeypatch.setattr(hd, "RESULT_FILE", str(tmp_path / "results.csv"))
    results = hd.get_hotspot_clusters(sample_stations, eps_km=5, min_samples=2)
    by_name = {row["station_name"]: row for row in results}

    assert by_name["A"]["is_hotspot_cluster"] is True
    assert by_name["A"]["is_pollution_hotspot"] is True

    assert by_name["B"]["is_hotspot_cluster"] is True
    assert by_name["B"]["is_pollution_hotspot"] is False
    assert by_name["B"]["hotspot_score"] == 0.0

    assert by_name["C"]["is_pollution_hotspot"] is True
    assert by_name["D"]["cluster"] == -1
    assert by_name["D"]["is_pollution_hotspot"] is False


@pytest.mark.parametrize("eps", [0, -1, float("inf"), float("nan")])
def test_rejects_invalid_eps(sample_stations, eps):
    with pytest.raises(ValueError, match="eps_km"):
        hd.get_hotspot_clusters(sample_stations, eps_km=eps)


@pytest.mark.parametrize("minimum", [0, -1, 1.5, True])
def test_rejects_invalid_min_samples(sample_stations, minimum):
    with pytest.raises(ValueError, match="min_samples"):
        hd.get_hotspot_clusters(sample_stations, min_samples=minimum)


def test_supports_pm25_unit_column_and_drops_invalid_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(hd, "RESULT_FILE", str(tmp_path / "results.csv"))
    data = pd.DataFrame([
        {"station": "A", "latitude": 18.52, "longitude": 73.85, "PM2.5 (?g/m?)": 75},
        {"station": "B", "latitude": 18.521, "longitude": 73.851, "PM2.5 (?g/m?)": 80},
        {"station": "bad", "latitude": float("inf"), "longitude": 73.85, "PM2.5 (?g/m?)": 90},
    ])
    results = hd.get_hotspot_clusters(data, eps_km=5, min_samples=2)

    assert len(results) == 2
    assert all(row["is_pollution_hotspot"] for row in results)


def test_empty_input_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(hd, "RESULT_FILE", str(tmp_path / "results.csv"))
    result = hd.get_hotspot_clusters(
        pd.DataFrame(columns=["station_name", "latitude", "longitude", "pm25"])
    )
    assert result == []
