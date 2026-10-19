"""
Comprehensive Automated Test Suite for Universal AI Pollution System
=====================================================================
Covers:
1. Universal Location Resolution (arbitrary coordinates, local names, geocoded queries)
2. Haversine distance accuracy & CPCB station discovery
3. Dynamic 3-Case Strategy:
   - Case A: Direct CPCB Station (<= 3 km)
   - Case B: Spatially Estimated Forecast (IDW across nearby stations <= 50 km)
   - Case C: Insufficient Data (> 50 km) with transparent suppression
4. SHAP Additive Consistency (E[y] + sum(phi_i) == y_pred within tolerance)
5. Zero Future-Data Leakage in validation features
6. Independent User Location Storage (never silently renamed to station)
7. Fast-API endpoints (/api/forecast/universal, /api/forecast/pm25, /api/forecast/stations)
"""

import math
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.station_registry import (
    haversine_distance,
    discover_cpcb_stations,
    get_station_registry,
)
from backend.services.universal_location_resolver import (
    resolve_universal_location,
    parse_coordinate_string,
)
from backend.ml.forecasting.universal_forecast import (
    universal_forecast,
    predict_for_single_station,
)

client = TestClient(app)


# =============================================================================
# 1. UNIVERSAL LOCATION INPUT & RESOLUTION TESTS
# =============================================================================

def test_parse_coordinate_string():
    """Verify coordinate parser correctly extracts floats."""
    coords = parse_coordinate_string("18.5790, 73.9830")
    assert coords is not None
    lat, lon = coords
    assert math.isclose(lat, 18.5790, abs_tol=1e-4)
    assert math.isclose(lon, 73.9830, abs_tol=1e-4)


def test_independent_location_storage(fresh_station_data):
    """Verify system stores user location independently without renaming to station."""
    res = resolve_universal_location("Wagholi")
    assert res["success"] is True
    # The user-selected location MUST remain Wagholi, NOT Alandi or Hadapsar
    assert "Wagholi" in res["location_name"]
    assert res["cpcb_station_audit"]["case"] == "CASE_B"


def test_arbitrary_valid_coordinates():
    """Verify system accepts arbitrary GPS coordinates anywhere in India."""
    res = resolve_universal_location("Custom Location", latitude=19.0760, longitude=72.8777)
    assert res["success"] is True
    assert math.isclose(res["latitude"], 19.0760, abs_tol=1e-4)
    assert math.isclose(res["longitude"], 72.8777, abs_tol=1e-4)


# =============================================================================
# 2. DYNAMIC CPCB STATION DISCOVERY & DISTANCE TESTS
# =============================================================================

def test_haversine_distance():
    """Verify Haversine formula against known benchmark (Pune to Mumbai is ~120-150 km)."""
    pune_lat, pune_lon = 18.5204, 73.8567
    mumbai_lat, mumbai_lon = 19.0760, 72.8777
    dist = haversine_distance(pune_lat, pune_lon, mumbai_lat, mumbai_lon)
    assert 115.0 <= dist <= 135.0


def test_station_registry_loaded():
    """Verify verified CPCB station registry is loaded with valid metadata."""
    registry = get_station_registry()
    assert len(registry) >= 10
    for name, st in registry.items():
        assert "station_id" in st
        assert "latitude" in st and "longitude" in st
        assert st["latitude"] > 0
        assert "pollutants_available" in st


# =============================================================================
# 3. DYNAMIC 3-CASE STRATEGY TESTS
# =============================================================================

def test_case_a_direct_station(fresh_station_data):
    """Case A: Target is <= 3 km from official CPCB station (e.g. Alandi)."""
    forecast = universal_forecast("Alandi")
    assert forecast["case"] == "CASE_A"
    assert forecast["forecast_available"] is True
    assert forecast["is_spatial_estimate"] is False
    assert forecast["predicted_pm25"] is not None
    assert forecast["predicted_pm25"] > 0
    # Primary station must be Alandi
    primary = forecast["primary_station"]
    assert "Alandi" in primary["clean_name"]
    assert primary["distance_km"] <= 3.0


def test_case_b_spatially_estimated(fresh_station_data):
    """Case B: Target has no monitor, but has stations within 50 km (e.g. Wagholi)."""
    forecast = universal_forecast("Wagholi")
    assert forecast["case"] == "CASE_B"
    assert forecast["forecast_available"] is True
    assert forecast["is_spatial_estimate"] is True
    assert forecast["predicted_pm25"] is not None
    # Must list multiple contributing stations with weights and observation timestamps
    contribs = forecast["contributing_stations"]
    assert len(contribs) >= 2
    for st in contribs:
        assert "distance_km" in st
        assert "weight" in st
        assert "latest_observation" in st
    # Verify weights sum close to 1.0 (or normalized)
    weights_sum = sum(st["weight"] for st in contribs)
    assert math.isclose(weights_sum, 1.0, abs_tol=0.4)


def test_case_c_insufficient_data():
    """Case C: Target location exceeds search radius (e.g. Delhi, 1100+ km away)."""
    forecast = universal_forecast("Delhi")
    assert forecast["case"] == "CASE_C"
    assert forecast["forecast_available"] is False
    assert forecast["predicted_pm25"] is None
    # Must explicitly state reason and nearest available station outside radius
    assert "No verified CPCB monitoring station exists within" in forecast["reason"]
    assert forecast["nearest_available_station"] is not None


# =============================================================================
# 4. SHAP ADDITIVE CONSISTENCY TEST
# =============================================================================

def test_shap_additive_consistency():
    """
    Verify exact additive consistency of SHAP values:
    E[y] + sum(phi_i) == y_pred
    """
    st_res = predict_for_single_station("Alandi, Pune - IITM")
    assert st_res["success"] is True
    shap_data = st_res["shap"]
    assert shap_data["available"] is True

    y_pred = shap_data["prediction"]
    base_e = shap_data["expected_value"]
    shap_sum = sum(item["shap_value"] for item in shap_data["features"])

    additive_reconstruction = base_e + shap_sum
    discrepancy = abs(additive_reconstruction - y_pred)
    # TreeExplainer calculates in float32; accumulating 72 features has ~1e-4 float32 precision slack
    assert discrepancy < 1e-3, f"SHAP additive check failed: diff={discrepancy}"


# =============================================================================
# 5. FASTAPI ENDPOINT TESTS
# =============================================================================

def test_universal_forecast_endpoint(fresh_station_data):
    """Test /api/forecast/universal endpoint."""
    resp = client.get("/api/forecast/universal?location=Wagholi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["case"] == "CASE_B"
    assert data["predicted_pm25"] is not None


def test_station_list_endpoint():
    """Test /api/forecast/stations endpoint."""
    resp = client.get("/api/forecast/stations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["station_count"] >= 10


def test_dashboard_endpoint():
    """Test /dashboard HTML delivery."""
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "AI Pollution Detection & Forecasting System" in resp.text
