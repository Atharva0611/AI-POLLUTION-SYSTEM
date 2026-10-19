from __future__ import annotations

import sys
from pathlib import Path

# Always make the project root importable when running this file directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.weather_intelligence import get_weather_report
from backend.pune_intelligence.location_network import load_locations, resolve_query
from backend.pune_intelligence.engine import build_location_intelligence


def optional_local_xgboost(station: str):
    """
    Safely use the existing forecasting module if it exposes a compatible
    simple station-level prediction function.

    This adapter NEVER modifies the existing XGBoost code and NEVER lets
    an unavailable predictor break the Pune innovation report.
    """
    if not station:
        return {
            "available": False,
            "reason": "No representative CPCB station is mapped to this locality.",
        }

    try:
        from backend.ml.forecasting import predict_forecast
    except Exception as exc:
        return {
            "available": False,
            "reason": f"Existing forecast module could not be imported: {exc}",
        }

    candidate_names = [
        "get_xgboost_forecast",
        "predict_forecast",
        "forecast_pm25",
        "predict_pm25",
        "predict_next_hour",
    ]

    for name in candidate_names:
        fn = getattr(predict_forecast, name, None)

        if not callable(fn):
            continue

        # Try the common calling patterns without changing the existing
        # forecasting module.
        for call in (
            lambda: fn(station),
            lambda: fn(station_name=station),
            lambda: fn(location=station),
        ):
            try:
                result = call()

                if isinstance(result, dict):
                    return {
                        "available": True,
                        "source": "Existing Pune XGBoost",
                        "function": name,
                        **result,
                    }

                return {
                    "available": True,
                    "source": "Existing Pune XGBoost",
                    "function": name,
                    "prediction": result,
                }

            except TypeError:
                continue
            except Exception as exc:
                return {
                    "available": False,
                    "source": "Existing Pune XGBoost",
                    "function": name,
                    "reason": str(exc),
                }

    return {
        "available": False,
        "source": "Existing Pune XGBoost",
        "reason": (
            "predict_forecast.py does not expose a compatible simple "
            "station-level prediction function. The innovation report "
            "continues using WeatherAPI and the other Pune intelligence modules."
        ),
    }


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Pune 100+ locality environmental intelligence"
    )
    parser.add_argument("location")
    args = parser.parse_args()

    locations = load_locations()
    query = args.location.strip().lower()

    rows = locations[
        locations["location"].astype(str).str.lower() == query
    ]

    if rows.empty:
        rows = locations[
            locations["location"]
            .astype(str)
            .str.lower()
            .str.contains(query, regex=False, na=False)
        ]

    if rows.empty:
        raise SystemExit(
            f"'{args.location}' was not found in the Pune 100+ locality network."
        )

    row = rows.iloc[0].to_dict()

    location_name = str(row["location"])
    weather_query = resolve_query(row)
    station = str(row.get("representative_cpcb_station") or "").strip()

    print()
    print("=" * 64)
    print("PUNE LOCALITY ENVIRONMENTAL INTELLIGENCE")
    print("=" * 64)
    print(f"Location: {location_name}")
    print(f"Weather query: {weather_query}")
    print(f"Representative CPCB station: {station or 'None'}")
    print()

    print("Getting WeatherAPI environment data...")
    environment = get_weather_report(weather_query, days=1)

    print("Checking existing Pune XGBoost...")
    environment["xgboost"] = optional_local_xgboost(station)

    print("Building innovation intelligence...")
    intelligence = build_location_intelligence(
        environment,
        location=location_name,
        representative_station=station or None,
    )

    result = {
        "environment": environment,
        "intelligence": intelligence,
    }

    print()
    print("=" * 64)
    print("MAJOR FACTORS")
    print("=" * 64)

    for item in intelligence["factor_fingerprint"]["top_factors"]:
        print(
            f"- {item['factor']}: "
            f"{item['score']}"
        )

    print()
    print("=" * 64)
    print("ENVIRONMENTAL SCORE")
    print("=" * 64)

    score = intelligence["environmental_score"]
    print(f"Score: {score['score']}")
    print(f"Band : {score['band']}")

    print()
    print("=" * 64)
    print("FORECAST TREND")
    print("=" * 64)

    print(intelligence["next_hour_signal"])

    print()
    print("=" * 64)
    print("POLICY → ACTION")
    print("=" * 64)

    for action in intelligence["policy_to_action"]["actions"]:
        print(
            f"[{action['priority']}] "
            f"{action['action']}"
        )

    print()
    print("=" * 64)
    print("INTERVENTION SIMULATOR")
    print("=" * 64)

    print(json.dumps(
        intelligence["intervention_simulator"],
        indent=2,
        ensure_ascii=False,
    ))

    print()
    print("=" * 64)
    print("XGBOOST STATUS")
    print("=" * 64)

    print(json.dumps(
        environment["xgboost"],
        indent=2,
        ensure_ascii=False,
        default=str,
    ))

    print()
    print("=" * 64)


if __name__ == "__main__":
    main()
