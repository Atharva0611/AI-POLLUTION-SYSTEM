from pathlib import Path
import os
import math
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

MAPPING_FILES = [
    ROOT / "data" / "processed" / "pune_100_locations_mapped.csv",
    ROOT / "data" / "processed" / "pune_50_cpcb_mapped_locations.csv",
    ROOT / "data" / "processed" / "pune_100_locations.csv",
]

API_URL = "https://api.weatherapi.com/v1/forecast.json"


def num(x):
    try:
        if x is None or pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def clean(x):
    if x is None or pd.isna(x):
        return None
    x = str(x).strip()
    if x.lower() in {"", "nan", "none", "null"}:
        return None
    return x


def norm(x):
    return " ".join(str(x).lower().replace("_", " ").split())


def load_locations():
    for path in MAPPING_FILES:
        if not path.exists():
            continue

        df = pd.read_csv(path)

        rename = {}

        for c in df.columns:
            n = norm(c)

            if n in {"location", "locality", "pune locality", "name"}:
                rename[c] = "location"

            elif n in {
                "representative cpcb station",
                "representative station",
                "cpcb station",
                "station",
            }:
                rename[c] = "representative_cpcb_station"

            elif n in {"latitude", "lat"}:
                rename[c] = "latitude"

            elif n in {"longitude", "lon", "lng"}:
                rename[c] = "longitude"

        df = df.rename(columns=rename)

        if "location" not in df.columns:
            continue

        if "representative_cpcb_station" not in df.columns:
            df["representative_cpcb_station"] = None

        return df

    return None


def resolve_location(user_location):
    df = load_locations()

    result = {
        "requested": user_location,
        "matched": user_location,
        "cpcb_station": None,
        "latitude": None,
        "longitude": None,
        "mapping_found": False,
    }

    if df is None:
        return result

    q = norm(user_location)
    names = df["location"].map(norm)

    # Exact match
    rows = df[names == q]

    # Partial match
    if rows.empty:
        rows = df[
            names.map(
                lambda x: x in q or q in x
            )
        ]

    if rows.empty:
        return result

    row = rows.iloc[0]

    result["matched"] = clean(row.get("location")) or user_location
    result["cpcb_station"] = clean(
        row.get("representative_cpcb_station")
    )
    result["latitude"] = num(row.get("latitude"))
    result["longitude"] = num(row.get("longitude"))
    result["mapping_found"] = True

    return result


def get_weather(resolved):
    load_dotenv(ROOT / ".env")

    key = os.getenv("WEATHER_API_KEY")

    if not key:
        raise RuntimeError(
            "WEATHER_API_KEY missing from .env"
        )

    lat = resolved.get("latitude")
    lon = resolved.get("longitude")

    if lat is not None and lon is not None:
        query = f"{lat},{lon}"
    else:
        query = (
            f"{resolved['matched']}, "
            "Pune, Maharashtra, India"
        )

    params = {
        "key": key,
        "q": query,
        "days": 1,
        "aqi": "yes",
        "alerts": "no",
    }

    r = requests.get(
        API_URL,
        params=params,
        timeout=30,
    )

    try:
        data = r.json()
    except Exception:
        raise RuntimeError(
            f"WeatherAPI returned HTTP {r.status_code}"
        )

    if not r.ok:
        raise RuntimeError(
            f"WeatherAPI HTTP {r.status_code}: "
            f"{data.get('error', data)}"
        )

    if "error" in data:
        raise RuntimeError(
            f"WeatherAPI error: {data['error']}"
        )

    return data


def get_current(data):
    c = data.get("current", {})
    aq = c.get("air_quality", {}) or {}

    return {
        "pm2_5": num(aq.get("pm2_5")),
        "pm10": num(aq.get("pm10")),
        "no2": num(aq.get("no2")),
        "so2": num(aq.get("so2")),
        "co": num(aq.get("co")),
        "o3": num(aq.get("o3")),
        "temperature": num(c.get("temp_c")),
        "humidity": num(c.get("humidity")),
        "wind": num(c.get("wind_kph")),
        "rain": num(c.get("precip_mm")),
        "pressure": num(c.get("pressure_mb")),
        "condition": clean(
            c.get("condition", {}).get("text")
        ),
    }


def get_next_pm25(data):
    location = data.get("location", {})
    localtime = location.get("localtime")

    hours = []

    for day in (
        data.get("forecast", {})
        .get("forecastday", [])
    ):
        for h in day.get("hour", []):
            if not h.get("time"):
                continue

            aq = h.get("air_quality", {}) or {}

            pm = num(aq.get("pm2_5"))

            if pm is None:
                continue

            hours.append({
                "time": h["time"],
                "pm25": pm,
            })

    if not hours:
        return None

    if localtime:
        future = [
            x for x in hours
            if x["time"] > localtime
        ]

        if future:
            return future[0]["pm25"]

    return hours[0]["pm25"]


def prediction(current, weather_prediction):
    pm = current["pm2_5"]

    if weather_prediction is not None:
        if pm is None:
            trend = "WeatherAPI forecast available"
        elif weather_prediction > pm + 2:
            trend = "Likely to increase"
        elif weather_prediction < pm - 2:
            trend = "Likely to decrease"
        else:
            trend = "Likely to remain stable"

        return {
            "value": weather_prediction,
            "trend": trend,
            "type": "WeatherAPI hourly forecast",
        }

    # Transparent fallback when AQ forecast is unavailable.
    score = 0
    reasons = []

    if pm is not None:
        if pm >= 60:
            score += 2
            reasons.append(
                "existing PM2.5 concentration is elevated"
            )
        elif pm >= 30:
            score += 1
            reasons.append(
                "existing PM2.5 concentration is moderate"
            )

    if current["wind"] is not None:
        if current["wind"] < 5:
            score += 2
            reasons.append(
                "low wind can reduce pollutant dispersion"
            )
        elif current["wind"] < 10:
            score += 1
            reasons.append(
                "relatively weak wind may limit dispersion"
            )

    if current["humidity"] is not None:
        if current["humidity"] >= 75:
            score += 1
            reasons.append(
                "high humidity is present"
            )

    if current["rain"] is not None:
        if current["rain"] <= 0.1:
            score += 1
            reasons.append(
                "little or no rainfall"
            )

    if score >= 5:
        trend = "Likely to remain elevated"
    elif score >= 3:
        trend = "May remain elevated"
    else:
        trend = "Likely to remain stable or improve"

    return {
        "value": pm,
        "trend": trend,
        "type": "Indicative weather-condition outlook",
        "reasons": reasons,
    }


def recommendations(current, trend):
    actions = []

    pm = current["pm2_5"]
    wind = current["wind"]
    rain = current["rain"]

    elevated = (
        "elevated" in trend.lower()
        or (
            pm is not None
            and pm > 60
        )
    )

    if elevated:
        actions.append(
            "Reduce prolonged outdoor exposure "
            "during the higher-pollution period."
        )

    if wind is not None and wind < 5:
        actions.append(
            "Prioritize dust-control measures "
            "near active construction and roadwork."
        )

    if rain is not None and rain <= 0.1:
        actions.append(
            "Control resuspended road dust "
            "in heavily trafficked areas."
        )

    if not actions:
        actions.append(
            "Continue routine monitoring and reassess "
            "if PM2.5 or PM10 increases."
        )

    return actions


def generate_report(location):
    resolved = resolve_location(location)

    weather = get_weather(resolved)
    current = get_current(weather)

    next_pm25 = get_next_pm25(weather)

    pred = prediction(
        current,
        next_pm25
    )

    station = resolved["cpcb_station"]

    if station:
        source = "WeatherAPI + representative CPCB station"
        station_text = station
    else:
        source = "WeatherAPI"
        station_text = "Not available"

    actions = recommendations(
        current,
        pred["trend"]
    )

    report = {
        "location": resolved["matched"],
        "latitude": weather.get(
            "location", {}
        ).get("lat"),
        "longitude": weather.get(
            "location", {}
        ).get("lon"),
        "current": current,
        "prediction": pred,
        "representative_cpcb_station": station,
        "forecast_source": source,
        "recommendations": actions,
    }

    return report


def print_report(report):
    c = report["current"]
    p = report["prediction"]

    print()
    print("=" * 70)
    print(
        f"{report['location']} — Pollution Intelligence"
    )
    print("=" * 70)

    print()
    print("CURRENT CONDITIONS")
    print("-" * 70)

    print(
        f"PM2.5: "
        f"{c['pm2_5']:.1f} µg/m³"
        if c["pm2_5"] is not None
        else "PM2.5: unavailable"
    )

    print(
        f"PM10: "
        f"{c['pm10']:.1f} µg/m³"
        if c["pm10"] is not None
        else "PM10: unavailable"
    )

    print(
        f"Temperature: "
        f"{c['temperature']:.1f} °C"
        if c["temperature"] is not None
        else "Temperature: unavailable"
    )

    print(
        f"Humidity: "
        f"{c['humidity']:.0f}%"
        if c["humidity"] is not None
        else "Humidity: unavailable"
    )

    if c["wind"] is not None:
        wind_level = (
            "Low"
            if c["wind"] < 5
            else "Moderate"
            if c["wind"] < 15
            else "High"
        )

        print(
            f"Wind: {c['wind']:.1f} km/h — {wind_level}"
        )
    else:
        print("Wind: unavailable")

    print(
        f"Rainfall: "
        f"{c['rain']:.1f} mm"
        if c["rain"] is not None
        else "Rainfall: unavailable"
    )

    print()
    print("NEAR-TERM PREDICTION")
    print("-" * 70)

    if p["value"] is not None:
        print(
            f"PM2.5 prediction: "
            f"{p['value']:.1f} µg/m³"
        )
    else:
        print("PM2.5 prediction: unavailable")

    print(f"Trend: {p['trend']}")

    if p.get("reasons"):
        print()
        print("LIKELY CONDITIONS")
        print("-" * 70)

        for reason in p["reasons"]:
            print(f"- {reason}")

    print()
    print("RECOMMENDATIONS")
    print("-" * 70)

    for action in report["recommendations"]:
        print(f"- {action}")

    print()
    print("DATA SOURCE")
    print("-" * 70)

    print(
        f"Forecast source: "
        f"{report['forecast_source']}"
    )

    print(
        f"Representative CPCB station: "
        f"{report['representative_cpcb_station']
          or 'Not available'}"
    )

    if report["representative_cpcb_station"]:
        print(
            "Note: this locality is mapped to a "
            "representative station; it is not an "
            "independent CPCB monitoring station."
        )
    else:
        print(
            "Fallback used: WeatherAPI current air "
            "quality + WeatherAPI hourly forecast."
        )

    print()
    print("=" * 70)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage:"
            "\n  python -m backend.services.pune_pollution_fallback Hinjewadi"
        )
        raise SystemExit(1)

    location = " ".join(sys.argv[1:])

    try:
        result = generate_report(location)
        print_report(result)
    except Exception as e:
        print()
        print("ERROR:", e)
        raise
