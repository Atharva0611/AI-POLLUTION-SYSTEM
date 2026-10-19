from __future__ import annotations

from typing import Any
import math


# ============================================================
# GENERIC HELPERS
# ============================================================

def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    except Exception:
        return None


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _first_number(*values) -> float | None:
    for value in values:
        result = _num(value)
        if result is not None:
            return result
    return None


# ============================================================
# ENVIRONMENT EXTRACTION
# ============================================================

def _get_current(environment: dict) -> dict:
    current = environment.get("current")

    if isinstance(current, dict):
        return current

    return {}


def _get_pm25(environment: dict) -> float | None:
    current = _get_current(environment)

    prediction = environment.get("prediction")
    if isinstance(prediction, dict):
        prediction_value = prediction.get("pm2_5")

        if prediction_value is None:
            prediction_value = prediction.get("pm25")

        if prediction_value is not None:
            return _num(prediction_value)

    return _first_number(
        current.get("pm2_5"),
        current.get("pm25"),
        current.get("PM2.5"),
        current.get("PM25"),
        environment.get("pm2_5"),
        environment.get("pm25"),
        environment.get("predicted_pm25_next_1h"),
    )


def _get_pollutant(environment: dict, *names) -> float | None:
    current = _get_current(environment)

    values = []

    for name in names:
        values.append(current.get(name))
        values.append(environment.get(name))

    return _first_number(*values)


def _get_weather(environment: dict) -> dict:
    current = _get_current(environment)

    return {
        "temperature_c": _first_number(
            current.get("temperature_c"),
            current.get("temp_c"),
            current.get("temperature"),
        ),
        "humidity": _first_number(
            current.get("humidity"),
            current.get("relative_humidity"),
        ),
        "wind_speed_kph": _first_number(
            current.get("wind_speed_kph"),
            current.get("wind_kph"),
            current.get("wind_speed"),
        ),
        "rainfall_mm": _first_number(
            current.get("rainfall_mm"),
            current.get("precip_mm"),
            current.get("rain"),
        ),
        "visibility_km": _first_number(
            current.get("visibility_km"),
            current.get("vis_km"),
            current.get("visibility"),
        ),
        "pressure_mb": _first_number(
            current.get("pressure_mb"),
            current.get("pressure"),
        ),
    }


# ============================================================
# ENVIRONMENTAL SCORE
# ============================================================

def _pollution_component(pm25: float | None) -> float:
    if pm25 is None:
        return 50.0

    if pm25 <= 15:
        return 100.0
    if pm25 <= 30:
        return 85.0
    if pm25 <= 60:
        return 65.0
    if pm25 <= 90:
        return 40.0
    if pm25 <= 150:
        return 20.0

    return 5.0


def _weather_component(weather: dict) -> float:
    score = 70.0
    count = 0

    humidity = weather.get("humidity")
    wind = weather.get("wind_speed_kph")
    rain = weather.get("rainfall_mm")

    if humidity is not None:
        count += 1

        if humidity >= 80:
            score -= 5
        elif humidity <= 25:
            score -= 2
        else:
            score += 3

    if wind is not None:
        count += 1

        if wind < 5:
            score -= 10
        elif wind >= 20:
            score += 8
        else:
            score += 3

    if rain is not None:
        count += 1

        if rain > 0:
            score += 5

    if count == 0:
        return 70.0

    return max(0.0, min(100.0, score))


def _environmental_score(environment: dict) -> dict:
    pm25 = _get_pm25(environment)
    weather = _get_weather(environment)

    pollution = _pollution_component(pm25)
    weather_score = _weather_component(weather)

    score = round(
        pollution * 0.75 +
        weather_score * 0.25,
        2,
    )

    if score >= 80:
        category = "GOOD"
    elif score >= 60:
        category = "MODERATE"
    elif score >= 40:
        category = "POOR"
    elif score >= 20:
        category = "VERY POOR"
    else:
        category = "SEVERE"

    return {
        "available": True,
        "score": score,
        "category": category,
        "components": {
            "pollution_score": round(pollution, 2),
            "weather_dispersion_score": round(weather_score, 2),
        },
        "method": "rule_based_environmental_screening",
    }


# ============================================================
# ANOMALY ANALYSIS
# ============================================================

def _forecast_pm25_values(environment: dict) -> list[float]:
    values = []

    forecast = environment.get("forecast_24_hours")

    if isinstance(forecast, list):
        for item in forecast:
            if not isinstance(item, dict):
                continue

            value = _first_number(
                item.get("pm2_5"),
                item.get("pm25"),
                item.get("predicted_pm25"),
            )

            if value is not None:
                values.append(value)

    return values


def _anomaly_analysis(environment: dict) -> dict:
    pm25 = _get_pm25(environment)
    forecast_values = _forecast_pm25_values(environment)

    if pm25 is None:
        return {
            "available": False,
            "status": "no_pm25",
            "method": "rule_based",
            "message": "PM2.5 is not available, so anomaly screening cannot be performed.",
        }

    # --------------------------------------------------------
    # Preferred: compare current PM2.5 to available forecast
    # --------------------------------------------------------

    if len(forecast_values) >= 3:
        mean_value = sum(forecast_values) / len(forecast_values)

        variance = sum(
            (x - mean_value) ** 2
            for x in forecast_values
        ) / len(forecast_values)

        std_value = math.sqrt(variance)

        if std_value > 0:
            z_score = (pm25 - mean_value) / std_value

            if abs(z_score) >= 2:
                status = "ANOMALY_DETECTED"
            elif abs(z_score) >= 1:
                status = "ELEVATED_VARIATION"
            else:
                status = "NORMAL_VARIATION"

            return {
                "available": True,
                "method": "forecast_baseline_zscore",
                "status": status,
                "current_pm25": round(pm25, 2),
                "baseline_mean": round(mean_value, 2),
                "baseline_std": round(std_value, 2),
                "z_score": round(z_score, 2),
                "sample_count": len(forecast_values),
                "message": (
                    "Current PM2.5 was compared with the available "
                    "forecast PM2.5 baseline."
                ),
            }

    # --------------------------------------------------------
    # Fallback: operational pollution screening
    # --------------------------------------------------------

    if pm25 >= 150:
        status = "CRITICALLY_ELEVATED"
    elif pm25 >= 90:
        status = "HIGH_VARIATION"
    elif pm25 >= 60:
        status = "ELEVATED"
    else:
        status = "NO_RULE_BASED_ALERT"

    return {
        "available": True,
        "method": "rule_based_pm25_screening",
        "status": status,
        "current_pm25": round(pm25, 2),
        "thresholds": {
            "elevated": 60,
            "high": 90,
            "critical": 150,
        },
        "message": (
            "Historical monitoring data is not attached. "
            "This is an operational PM2.5 screening result, "
            "not a statistical anomaly score."
        ),
    }


# ============================================================
# SOURCE INDICATORS
# ============================================================

def _source_indicators(environment: dict) -> dict:
    pm25 = _get_pm25(environment)

    pm10 = _get_pollutant(
        environment,
        "pm10",
        "PM10",
    )

    no2 = _get_pollutant(
        environment,
        "no2",
        "NO2",
    )

    so2 = _get_pollutant(
        environment,
        "so2",
        "SO2",
    )

    co = _get_pollutant(
        environment,
        "co",
        "CO",
    )

    weather = _get_weather(environment)

    indicators = []
    evidence = []

    if pm10 is not None and pm25 is not None:
        if pm10 > pm25 * 2:
            indicators.append("particulate_dust_signal")
            evidence.append(
                "PM10 is substantially higher than PM2.5."
            )

    if no2 is not None:
        if no2 > 80:
            indicators.append("traffic_combustion_signal")
            evidence.append(
                "NO2 concentration is elevated."
            )

    if co is not None:
        if co > 2:
            indicators.append("combustion_signal")
            evidence.append(
                "CO concentration is elevated."
            )

    if so2 is not None:
        if so2 > 80:
            indicators.append("sulfur_emission_signal")
            evidence.append(
                "SO2 concentration is elevated."
            )

    wind = weather.get("wind_speed_kph")

    if wind is not None and wind < 5:
        indicators.append("low_dispersion_signal")
        evidence.append(
            "Low wind speed can reduce atmospheric dispersion."
        )

    if not indicators:
        indicators.append("no_strong_screening_signal")
        evidence.append(
            "Available live data does not show a strong screening indicator."
        )

    return {
        "available": True,
        "method": "rule_based_source_indicators",
        "indicators": indicators,
        "evidence": evidence,
        "warning": (
            "These are screening indicators, not definitive source "
            "apportionment."
        ),
    }


# ============================================================
# HOTSPOT ANALYSIS
# ============================================================

def _extract_spatial_points(environment: dict) -> list[dict]:
    possible = []

    for key in (
        "stations",
        "monitoring_stations",
        "locations",
        "spatial_points",
        "points",
    ):
        value = environment.get(key)

        if isinstance(value, list):
            possible.extend(value)

    valid = []

    for item in possible:
        if not isinstance(item, dict):
            continue

        lat = _first_number(
            item.get("latitude"),
            item.get("lat"),
        )

        lon = _first_number(
            item.get("longitude"),
            item.get("lon"),
            item.get("lng"),
        )

        pm25 = _first_number(
            item.get("pm2_5"),
            item.get("pm25"),
            item.get("PM2.5"),
        )

        if lat is not None and lon is not None:
            valid.append({
                "latitude": lat,
                "longitude": lon,
                "pm25": pm25,
                "name": item.get("name") or item.get("station_name"),
            })

    return valid


def _hotspot_analysis(environment: dict) -> dict:
    points = _extract_spatial_points(environment)

    if len(points) < 3:
        return {
            "available": False,
            "status": "INSUFFICIENT_SPATIAL_DATA",
            "method": "DBSCAN",
            "points_available": len(points),
            "minimum_points_required": 3,
            "message": (
                "Hotspot detection needs multiple geographic monitoring "
                "points. Current WeatherAPI response represents one "
                "location, so a spatial hotspot cannot be calculated yet."
            ),
        }

    try:
        from sklearn.cluster import DBSCAN
    except Exception:
        return {
            "available": False,
            "status": "SKLEARN_UNAVAILABLE",
            "method": "DBSCAN",
            "points_available": len(points),
            "message": (
                "scikit-learn is not installed, so DBSCAN hotspot "
                "clustering cannot run."
            ),
        }

    coords = [
        [p["latitude"], p["longitude"]]
        for p in points
    ]

    model = DBSCAN(
        eps=0.03,
        min_samples=2,
    )

    labels = model.fit_predict(coords)

    clusters = {}

    for point, label in zip(points, labels):
        if label == -1:
            continue

        clusters.setdefault(int(label), []).append(point)

    result_clusters = []

    for cluster_id, cluster_points in clusters.items():
        pm_values = [
            p["pm25"]
            for p in cluster_points
            if p.get("pm25") is not None
        ]

        result_clusters.append({
            "cluster_id": cluster_id,
            "point_count": len(cluster_points),
            "center_latitude": round(
                sum(p["latitude"] for p in cluster_points)
                / len(cluster_points),
                6,
            ),
            "center_longitude": round(
                sum(p["longitude"] for p in cluster_points)
                / len(cluster_points),
                6,
            ),
            "average_pm25": (
                round(sum(pm_values) / len(pm_values), 2)
                if pm_values
                else None
            ),
        })

    return {
        "available": True,
        "status": (
            "HOTSPOTS_DETECTED"
            if result_clusters
            else "NO_DENSE_CLUSTER_DETECTED"
        ),
        "method": "DBSCAN",
        "points_available": len(points),
        "cluster_count": len(result_clusters),
        "clusters": result_clusters,
    }


# ============================================================
# SHAP
# ============================================================

def _shap_analysis(
    model: Any = None,
    feature_row: Any = None,
    feature_names: list[str] | None = None,
) -> dict:
    if model is None:
        return {
            "available": False,
            "status": "MODEL_NOT_ATTACHED",
            "method": "SHAP",
            "message": (
                "A trained XGBoost model has not been attached to the "
                "intelligence engine. SHAP values cannot be calculated."
            ),
        }

    if feature_row is None:
        return {
            "available": False,
            "status": "FEATURE_ROW_MISSING",
            "method": "SHAP",
            "message": (
                "The model exists, but its prediction feature row was "
                "not supplied."
            ),
        }

    try:
        import shap

        explainer = shap.Explainer(model)
        values = explainer(feature_row)

        raw_values = values.values

        if hasattr(raw_values, "ndim") and raw_values.ndim == 2:
            raw_values = raw_values[0]

        raw_values = list(raw_values)

        if feature_names is None:
            feature_names = [
                f"feature_{i}"
                for i in range(len(raw_values))
            ]

        pairs = []

        for name, value in zip(feature_names, raw_values):
            numeric = _num(value)

            if numeric is None:
                continue

            pairs.append({
                "feature": name,
                "shap_value": round(numeric, 6),
                "absolute_impact": round(abs(numeric), 6),
                "direction": (
                    "increases_prediction"
                    if numeric > 0
                    else "decreases_prediction"
                    if numeric < 0
                    else "neutral"
                ),
            })

        pairs.sort(
            key=lambda x: x["absolute_impact"],
            reverse=True,
        )

        return {
            "available": True,
            "status": "SHAP_AVAILABLE",
            "method": "SHAP",
            "top_features": pairs[:10],
            "message": (
                "Feature contribution calculated from the attached "
                "trained model."
            ),
        }

    except ImportError:
        return {
            "available": False,
            "status": "SHAP_NOT_INSTALLED",
            "method": "SHAP",
            "message": (
                "The SHAP package is not installed."
            ),
        }

    except Exception as exc:
        return {
            "available": False,
            "status": "SHAP_CALCULATION_ERROR",
            "method": "SHAP",
            "message": str(exc),
        }


# ============================================================
# INTERVENTION SIMULATION
# ============================================================

def _intervention_simulation(environment: dict) -> dict:
    pm25 = _get_pm25(environment)

    if pm25 is None:
        return {
            "available": False,
            "status": "NO_PM25",
            "method": "SCENARIO_SIMULATION",
            "message": (
                "PM2.5 is unavailable, so an intervention scenario "
                "cannot be calculated."
            ),
        }

    scenarios = []

    # These are scenario assumptions, not measured effects.
    reductions = [
        ("Low intervention", 0.10),
        ("Moderate intervention", 0.20),
        ("Strong intervention", 0.30),
        ("Aggressive intervention", 0.40),
    ]

    for label, reduction in reductions:
        estimated = pm25 * (1.0 - reduction)

        scenarios.append({
            "scenario": label,
            "assumed_reduction_percent": int(reduction * 100),
            "current_pm25": round(pm25, 2),
            "estimated_pm25": round(estimated, 2),
            "estimated_reduction": round(
                pm25 - estimated,
                2,
            ),
        })

    return {
        "available": True,
        "status": "SCENARIOS_CALCULATED",
        "method": "SCENARIO_SIMULATION",
        "scenarios": scenarios,
        "warning": (
            "These are hypothetical percentage-reduction scenarios. "
            "They are not measured causal effects and should not be "
            "presented as policy impact estimates."
        ),
    }


# ============================================================
# MAIN INTELLIGENCE ENGINE
# ============================================================

def build_intelligence(
    environment: dict,
    location: str | None = None,
    model: Any = None,
    feature_row: Any = None,
    feature_names: list[str] | None = None,
) -> dict:

    environment = _safe_dict(environment)

    pm25 = _get_pm25(environment)

    result = {
        "available": True,
        "location": location or "Unknown",
        "analysis_status": "COMPLETED",
        "data_mode": "LIVE_ENVIRONMENTAL_DATA",
        "pm25": pm25,

        "environmental_score": _environmental_score(
            environment
        ),

        "source_indicators": _source_indicators(
            environment
        ),

        "anomaly": _anomaly_analysis(
            environment
        ),

        "hotspot": _hotspot_analysis(
            environment
        ),

        "shap": _shap_analysis(
            model=model,
            feature_row=feature_row,
            feature_names=feature_names,
        ),

        "intervention_simulation": _intervention_simulation(
            environment
        ),
    }

    return result
