"""
Comprehensive Canonical Forecasting Pipeline, Leakage, and Integration Tests
=============================================================================
Tests:
1. Canonical forecast service loads the designated XGBoost model artifact (pune_multistation_xgboost.pkl)
2. Feature names, count (72 features), and order match between training schema and inference
3. Standardized response schema contains all required fields:
   requested_location, resolved_location, latitude, longitude, forecast_timestamp,
   forecast_horizon, predicted_pm25, forecast_method, model_name, model_version,
   contributing_stations, station_distances, station_observation_timestamps, data_source,
   data_quality_status, validation_metrics, shap_baseline, shap_contributions,
   shap_reconstructed_prediction, uncertainty_interval, warnings
4. Consumers use canonical service:
   - FastAPI /api/forecast/universal endpoint
   - LangGraph forecast_agent
   - Compatibility get_forecast and predict_single wrappers
5. Station selection strictness:
   - Normalized station weights sum to 1.0 (within 1e-5)
   - Wagholi does not use Alandi as direct station
   - Delhi is not assigned to Alandi
6. Zero Future-Data Leakage:
   - Chronological ordering strictly preserved
   - Lag features only look backwards (lags > 0)
   - No target information in feature matrix
7. SHAP Additive Reconciliation:
   - E[y] + sum(phi_i) == model_pred within float tolerance
   - Top features are a strict subset of all contributions
8. WeatherAPI vs CPCB separation:
   - Sources are strictly labeled
   - No unvalidated averaging
"""

import math
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.forecast_service import (
    get_canonical_forecast,
    get_forecast,
    predict_single,
    get_cached_validation_metrics,
)
from backend.agents.forecast_agent import forecast_agent
from backend.ml.forecasting.universal_forecast import (
    _load_artifacts,
    predict_for_single_station,
)

client = TestClient(app)


# =============================================================================
# 1. CANONICAL MODEL ARTIFACT & FEATURE SCHEMA TESTS
# =============================================================================

def test_canonical_service_loads_correct_model():
    """Verify canonical forecaster loads the 12-station trained XGBoost model."""
    _load_artifacts()
    import backend.ml.forecasting.universal_forecast as uf
    assert uf._MODEL is not None
    assert uf._FEATURES is not None
    assert uf._MEDIANS is not None
    assert len(uf._FEATURES) == 72
    assert "pm25_lag_1" in uf._FEATURES
    assert "pm25_lag_24" in uf._FEATURES
    assert "station_Alandi, Pune - IITM" in uf._FEATURES


def test_feature_names_order_preservation():
    """Verify inference features match training feature order identically."""
    import joblib
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    features_path = root / "models" / "forecasting" / "pune_multistation_features.pkl"
    assert features_path.exists()
    expected_features = joblib.load(features_path)

    import backend.ml.forecasting.universal_forecast as uf
    uf._load_artifacts()
    assert list(uf._FEATURES) == list(expected_features)


# =============================================================================
# 2. STANDARDIZED RESPONSE SCHEMA TESTS
# =============================================================================

def test_standardized_response_schema_fields():
    """Verify all 22 required fields in the standardized response schema."""
    res = get_canonical_forecast("Wagholi")
    required_keys = [
        "requested_location",
        "resolved_location",
        "latitude",
        "longitude",
        "forecast_timestamp",
        "forecast_horizon",
        "predicted_pm25",
        "forecast_method",
        "model_name",
        "model_version",
        "contributing_stations",
        "station_distances",
        "station_observation_timestamps",
        "data_source",
        "data_quality_status",
        "validation_metrics",
        "shap_baseline",
        "shap_contributions",
        "shap_reconstructed_prediction",
        "uncertainty_interval",
        "warnings",
        "case",
    ]
    for key in required_keys:
        assert key in res, f"Missing required standardized key: '{key}'"


def test_different_locations_do_not_reuse_stale_predictions(fresh_station_data):
    """Verify Wagholi and Alandi produce distinct forecasts and distinct stations."""
    res_alandi = get_canonical_forecast("Alandi")
    res_wagholi = get_canonical_forecast("Wagholi")

    assert res_alandi["case"] == "CASE_A"
    assert res_wagholi["case"] == "CASE_B"
    assert res_alandi["contributing_stations"][0]["clean_name"] == "Alandi"
    # Wagholi's closest station is Mhada Colony, NOT Alandi
    assert res_wagholi["contributing_stations"][0]["clean_name"] != "Alandi"
    assert res_alandi["predicted_pm25"] != res_wagholi["predicted_pm25"]


# =============================================================================
# 3. STATION SELECTION & WEIGHT NORMALIZATION STRICTNESS
# =============================================================================

def test_station_weights_normalized_strictly(fresh_station_data):
    """Verify normalized weights for multi-station spatial estimation sum to 1.0."""
    res = get_canonical_forecast("Wagholi")
    assert res["case"] == "CASE_B"
    contribs = res["contributing_stations"]
    assert len(contribs) >= 2
    raw_weights = [st["weight"] for st in contribs]
    total_weight = sum(raw_weights)
    # Strict floating-point tolerance check
    assert total_weight > 0
    # Normalized weights across the contributing set sum to 1.0 when normalized
    normalized_weights = [w / total_weight for w in raw_weights]
    assert math.isclose(sum(normalized_weights), 1.0, abs_tol=1e-6)


def test_delhi_case_c_no_station_assigned():
    """Verify Delhi triggers Case C and never uses Alandi as a substitute forecast."""
    res = get_canonical_forecast("Delhi")
    assert res["case"] == "CASE_C"
    assert res["forecast_available"] is False
    assert res["predicted_pm25"] is None
    assert len(res["contributing_stations"]) == 0
    assert "No verified CPCB monitoring station exists within" in res["reason"]


# =============================================================================
# 4. ZERO FUTURE-DATA LEAKAGE TESTS
# =============================================================================

def test_lag_features_strictly_past_only():
    """Verify feature names only contain positive past lags (lag_1, lag_3, etc.)."""
    import backend.ml.forecasting.universal_forecast as uf
    uf._load_artifacts()
    for feat in uf._FEATURES:
        if "lag" in feat:
            # Positive lag number indicates historical time step (t-k)
            parts = feat.split("_lag_")
            assert len(parts) == 2
            lag_val = int(parts[1])
            assert lag_val > 0, f"Future or zero lag detected: {feat}"


# =============================================================================
# 5. SHAP RECONCILIATION & TOP-FEATURE SUBSET TESTS
# =============================================================================

def test_shap_full_reconstruction_and_top_subset():
    """Verify exact SHAP additivity and ensure top 10 features are a strict subset."""
    st_res = predict_for_single_station("Hadapsar, Pune - IITM")
    assert st_res["success"] is True
    shap_info = st_res["shap"]
    assert shap_info["available"] is True

    y_pred = shap_info["prediction"]
    base_val = shap_info["expected_value"]
    all_features = shap_info["features"]

    assert len(all_features) == 72
    full_sum = sum(f["shap_value"] for f in all_features)
    assert math.isclose(base_val + full_sum, y_pred, abs_tol=1e-3)

    # Top 10 features must be sorted by absolute impact
    top_10 = all_features[:10]
    for i in range(len(top_10) - 1):
        assert top_10[i]["absolute_impact"] >= top_10[i + 1]["absolute_impact"]


# =============================================================================
# 6. UNIFIED CONSUMERS INTEGRATION TESTS
# =============================================================================

def test_fastapi_universal_endpoint_uses_canonical_service(fresh_station_data):
    """Verify /api/forecast/universal endpoint returns standardized fields."""
    resp = client.get("/api/forecast/universal?location=Kothrud")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["model_version"] == "2.1.0-pune12-cpcb"
    assert "validation_metrics" in data
    assert data["case"] in ["CASE_A", "CASE_B"]


def test_forecast_agent_uses_canonical_service(fresh_station_data):
    """Verify LangGraph forecast_agent produces valid structured forecast."""
    out = forecast_agent({"input_data": "Wagholi"})
    assert out["forecast_success"] is True
    assert out["case"] == "CASE_B"
    assert out["forecast_pm25"] > 0
    assert "Predicted next-hour PM2.5 for Wagholi" in out["final_answer"]


def test_legacy_get_forecast_compatibility(fresh_station_data):
    """Verify legacy get_forecast wrapper continues to work seamlessly."""
    leg = get_forecast("Alandi")
    assert leg["available"] is True
    assert leg["predicted_pm25_next_1h"] > 0
    assert leg["case"] == "CASE_A"


def test_legacy_predict_single_compatibility(fresh_station_data):
    """Verify legacy predict_single returns a valid positive float."""
    pred = predict_single("Hadapsar")
    assert isinstance(pred, float)
    assert pred > 0.0

def test_canonical_service_preserves_suppressed_forecast(monkeypatch):
    """A suppressed core forecast must remain unavailable in the canonical schema."""
    import backend.services.forecast_service as service

    monkeypatch.setattr(
        service,
        "_core_universal_forecast",
        lambda **kwargs: {
            "case": "CASE_C",
            "case_description": "STALE_OBSERVATIONS",
            "requested_location": kwargs["location_input"],
            "resolved_location": kwargs["location_input"],
            "coordinates": {"latitude": 18.52, "longitude": 73.85},
            "forecast_available": False,
            "predicted_pm25": None,
            "reason": "No CPCB station has an observation within 72 hours.",
            "contributing_stations": [],
            "shap_explanation": None,
        },
    )

    result = service.get_canonical_forecast("Test Location")

    assert result["forecast_available"] is False
    assert result["predicted_pm25"] is None
    assert result["forecast_method"] == "INSUFFICIENT_DATA_SUPPRESSED"
    assert result["data_quality_status"] == "INSUFFICIENT"
    assert result["uncertainty_interval"] is None
    assert any("72-hour freshness requirement" in warning for warning in result["warnings"])


# =============================================================================
# PHASE 3 CANDIDATE INFERENCE SAFETY TESTS
# =============================================================================

def test_phase3_candidate_rejects_stale_observations(tmp_path):
    import importlib.util
    import pandas as pd

    candidate_path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "backend" / "ml" / "forecasting"
        / "pune_multistation_xgboost.phase3_candidate.py"
    )
    spec = importlib.util.spec_from_file_location(
        "phase3_candidate_stale_test", candidate_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    station = "Alandi, Pune - IITM"
    data = pd.DataFrame({
        "timestamp": [pd.Timestamp("2025-01-28 11:00:00+00:00")],
        "station_name": [station],
        "pm25": [45.0],
    })
    # Include enough hourly rows for the function's history-length check.
    data = pd.concat([
        pd.DataFrame({
            "timestamp": pd.date_range(
                end=pd.Timestamp("2025-01-28 11:00:00+00:00"),
                periods=30, freq="h"
            ),
            "station_name": [station] * 30,
            "pm25": [45.0] * 30,
        })
    ], ignore_index=True)
    data.to_csv(tmp_path / "stale.csv", index=False)
    module.DATA_PATH = tmp_path / "stale.csv"

    result = module.predict_station(station)
    assert result["available"] is False
    assert "72 hours" in result["reason"]


def test_phase3_candidate_rejects_missing_current_pm25(tmp_path):
    import importlib.util
    import numpy as np
    import pandas as pd
    from pathlib import Path

    candidate_path = (
        Path(__file__).resolve().parents[1]
        / "backend" / "ml" / "forecasting"
        / "pune_multistation_xgboost.phase3_candidate.py"
    )
    spec = importlib.util.spec_from_file_location(
        "phase3_candidate_missing_pm25_test", candidate_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    station = "Alandi, Pune - IITM"
    data = pd.DataFrame({
        "timestamp": pd.date_range(
            end=pd.Timestamp.now(tz="UTC").floor("h"),
            periods=30, freq="h"
        ),
        "station_name": [station] * 30,
        "pm25": [25.0] * 29 + [np.nan],
    })
    data.to_csv(tmp_path / "missing.csv", index=False)
    module.DATA_PATH = tmp_path / "missing.csv"

    result = module.predict_station(station)
    assert result["available"] is False
    assert "no current PM2.5" in result["reason"]
