from pathlib import Path
from datetime import datetime
import json
import re

from backend.services.weather_intelligence import get_weather_report
from backend.services.forecast_integration import get_xgboost_forecast
from backend.services.decision_engine import get_decision
from backend.services.location_resolver import require_location
from backend.agents.policy_agent import answer_question


ROOT = Path(
    r"C:\final year project\AI-POLLUTION-SYSTEM"
)

REPORT_DIR = (
    ROOT
    / "data"
    / "reports"
)

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def safe_name(value):
    return re.sub(
        r"[^a-zA-Z0-9]+",
        "_",
        str(value)
    ).strip("_").lower()


def build_policy_query(
    location,
    current
):
    pm25 = current.get(
        "pm2_5"
    )

    try:
        pm25 = float(pm25)
    except (TypeError, ValueError):
        pm25 = None

    if pm25 is not None and pm25 >= 90:

        return (
            f"What measures can reduce very high "
            f"PM2.5 pollution in {location}?"
        )

    if pm25 is not None and pm25 >= 60:

        return (
            f"What measures can reduce high "
            f"PM2.5 pollution in {location}?"
        )

    return (
        "What measures can reduce air pollution "
        "and protect air quality?"
    )


def normalize_for_decision(current):
    """
    Convert the WeatherAPI field names to the field names
    already used by the recommendation/decision engine.
    """

    return {
        "pm2_5": current.get(
            "pm2_5"
        ),
        "pm10": current.get(
            "pm10"
        ),
        "no2": current.get(
            "no2"
        ),
        "so2": current.get(
            "so2"
        ),
        "co": current.get(
            "co"
        ),
        "o3": current.get(
            "o3"
        ),
        "temperature_c": current.get(
            "temperature_c"
        ),
        "feels_like_c": current.get(
            "feels_like_c"
        ),
        "humidity": current.get(
            "humidity"
        ),
        "rainfall_mm": current.get(
            "precipitation_mm"
        ),
        "wind_speed_kph": current.get(
            "wind_kph"
        ),
        "wind_direction": current.get(
            "wind_direction"
        ),
        "pressure_mb": current.get(
            "pressure_mb"
        ),
        "visibility_km": current.get(
            "visibility_km"
        ),
        "uv": current.get(
            "uv"
        ),
        "condition": current.get(
            "condition"
        ),
        "aqi": current.get(
            "cpcb_indicative_aqi"
        ),
        "aqi_category": current.get(
            "cpcb_indicative_category"
        ),
    }


def get_complete_environment_report(
    question
):
    """
    Single source of truth for a complete environmental request.

    Pipeline:
        question
          -> location resolver
          -> WeatherAPI current + hourly + daily
          -> XGBoost/ensemble
          -> decision/recommendations
          -> policy/RAG
          -> optional SHAP
          -> optional source analysis
    """

    location = require_location(
        question
    )

    # --------------------------------------------------------
    # 1. LIVE WEATHER + AIR QUALITY
    # --------------------------------------------------------

    weather = get_weather_report(
        location,
        days=3
    )

    current = weather.get(
        "current",
        {}
    )

    # --------------------------------------------------------
    # 2. XGBOOST / ENSEMBLE
    # --------------------------------------------------------

    try:

        ml_forecast = get_xgboost_forecast(
            location
        )

    except Exception as exc:

        ml_forecast = {
            "available": False,
            "location": location,
            "forecast_source": "unavailable",
            "reason": (
                f"XGBoost unavailable: "
                f"{type(exc).__name__}: {exc}"
            ),
        }

    # --------------------------------------------------------
    # IMPORTANT:
    # Every supported city should still have a live PM2.5
    # forecast from WeatherAPI, even when XGBoost has no
    # historical station for that city.
    # --------------------------------------------------------

    weather_hourly = weather.get(
        "hourly_forecast",
        []
    ) or []

    current_local_time = (
        weather.get(
            "location",
            {}
        ).get(
            "local_time"
        )
    )

    next_hour_item = None

    if weather_hourly:

        # WeatherAPI hourly forecast usually begins with the
        # current hour. Select the first usable future PM2.5.
        for item in weather_hourly:

            pm25 = item.get(
                "pm2_5"
            )

            if pm25 is None:
                continue

            item_time = str(
                item.get(
                    "time",
                    ""
                )
            )

            if (
                current_local_time
                and item_time
                and item_time > str(
                    current_local_time
                )[:16]
            ):
                next_hour_item = item
                break

        # Fallback to the first PM2.5-bearing forecast record.
        if next_hour_item is None:

            for item in weather_hourly:

                if item.get("pm2_5") is not None:

                    next_hour_item = item
                    break

    weatherapi_next_pm25 = None

    if next_hour_item:

        weatherapi_next_pm25 = (
            next_hour_item.get(
                "pm2_5"
            )
        )

    # XGBoost is valid only when your trained station model
    # actually supports this location.
    xgb_available = bool(
        isinstance(
            ml_forecast,
            dict
        )
        and ml_forecast.get(
            "available"
        )
        and ml_forecast.get(
            "predicted_pm25_next_1h"
        ) is not None
    )

    if not xgb_available:

        if weatherapi_next_pm25 is not None:

            ml_forecast = {
                "available": True,
                "location": location,
                "model_station": None,
                "forecast_source": "WeatherAPI",
                "predicted_pm25_next_1h":
                    weatherapi_next_pm25,
                "weatherapi_forecast_time":
                    next_hour_item.get(
                        "time"
                    ) if next_hour_item else None,
                "ensemble": {},
                "reason": (
                    "XGBoost has no trained historical station "
                    "for this location; using the live WeatherAPI "
                    "hourly PM2.5 forecast."
                ),
            }
        else:

            ml_forecast = {
                "available": False,
                "location": location,
                "model_station": None,
                "forecast_source": "unavailable",
                "predicted_pm25_next_1h": None,
                "ensemble": {},
                "reason": (
                    "Neither a supported XGBoost station nor a "
                    "usable WeatherAPI PM2.5 forecast was available."
                ),
            }

    # --------------------------------------------------------
    # 3. DECISION + RECOMMENDATIONS
    # --------------------------------------------------------

    decision_current = normalize_for_decision(
        current
    )

    try:

        decision = get_decision(
            location=location,
            current=decision_current,
            xgboost=ml_forecast
        )

    except Exception as exc:

        decision = {
            "warnings": [],
            "recommended_actions": [],
            "anomaly": {},
            "hotspot": {},
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }

    # --------------------------------------------------------
    # 4. POLICY / CONTROL MEASURES
    # --------------------------------------------------------

    policy = {}

    try:

        policy_query = build_policy_query(
            location,
            current
        )

        policy = answer_question(
            policy_query
        )

    except Exception as exc:

        policy = {
            "answer": (
                "Policy information unavailable: "
                f"{type(exc).__name__}: {exc}"
            ),
            "sources": [],
            "method": "policy unavailable",
        }

    # --------------------------------------------------------
    # 5. SHAP
    # --------------------------------------------------------

    shap_analysis = {}

    try:

        if ml_forecast.get("available"):

            model_station = (
                ml_forecast.get(
                    "model_station"
                )
            )

            if model_station:

                from backend.ml.explainability.shap_explainer import (
                    explain_prediction
                )

                shap_analysis = explain_prediction(
                    model_station
                )

    except Exception as exc:

        shap_analysis = {
            "status": "unavailable",
            "reason": (
                f"{type(exc).__name__}: {exc}"
            ),
        }

    # --------------------------------------------------------
    # 6. SOURCE ANALYSIS
    # --------------------------------------------------------

    source_analysis = {}

    try:

        model_station = (
            ml_forecast.get(
                "model_station"
            )
            if isinstance(
                ml_forecast,
                dict
            )
            else None
        )

        if model_station:

            from backend.ml.source_analysis import (
                analyze_source_indicators
            )

            source_analysis = (
                analyze_source_indicators(
                    model_station
                )
            )

    except Exception as exc:

        source_analysis = {
            "status": "unavailable",
            "reason": (
                f"{type(exc).__name__}: {exc}"
            ),
        }

    # --------------------------------------------------------
    # 7. FINAL REPORT OBJECT
    # --------------------------------------------------------

    report = {
        "generated_at": datetime.now().isoformat(),

        "question": question,

        "location": weather.get(
            "location",
            {
                "name": location
            }
        ),

        "current": current,

        "hourly_forecast": weather.get(
            "hourly_forecast",
            []
        ),

        "daily_forecast": weather.get(
            "daily_forecast",
            []
        ),

        "weather_alerts": weather.get(
            "alerts",
            []
        ),

        "ml_forecast": ml_forecast,

        "decision": decision,

        "policy": policy,

        "shap": shap_analysis,

        "source_analysis": source_analysis,

        "forecast_methodology": {
            "weather":
                "WeatherAPI realtime and provider forecast",
            "pm25_ml":
                "XGBoost next-hour forecast when a supported model station is available",
            "ensemble":
                "XGBoost + WeatherAPI only when both estimates are available",
            "aqi":
                "Indicative pollutant-subindex calculation; not automatically official CPCB AQI",
        },

        "accuracy_note": (
            "Forecast accuracy is not assumed from the provider name. "
            "The system reports forecast source and horizon. "
            "Final project accuracy must be measured against held-out observations."
        ),
    }

    # --------------------------------------------------------
    # 8. SAVE REPORT
    # --------------------------------------------------------

    filename = (
        safe_name(location)
        + "_environment_report.json"
    )

    output_file = (
        REPORT_DIR
        / filename
    )

    output_file.write_text(
        json.dumps(
            report,
            indent=2,
            default=str
        ),
        encoding="utf-8"
    )

    report["saved_report"] = str(
        output_file
    )

    return report
