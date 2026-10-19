from __future__ import annotations

from typing import Any, Dict, Optional
import math


def _num(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        x = float(value)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except (TypeError, ValueError):
        return None


def _recursive_find(data: Any, names: list[str]) -> Any:
    wanted = {
        str(x).lower().replace(".", "").replace("-", "_").replace(" ", "_")
        for x in names
    }

    if isinstance(data, dict):
        for key, value in data.items():
            normalized = (
                str(key).lower()
                .replace(".", "")
                .replace("-", "_")
                .replace(" ", "_")
            )
            if normalized in wanted:
                return value

        for value in data.values():
            found = _recursive_find(value, names)
            if found is not None:
                return found

    elif isinstance(data, list):
        for value in data:
            found = _recursive_find(value, names)
            if found is not None:
                return found

    return None


def _weather(report: Dict[str, Any]) -> Dict[str, Optional[float]]:
    return {
        "temperature": _num(
            _recursive_find(
                report,
                ["temperature", "temp_c", "temp"]
            )
        ),
        "humidity": _num(
            _recursive_find(
                report,
                ["humidity", "humidity_pct"]
            )
        ),
        "wind_speed": _num(
            _recursive_find(
                report,
                ["wind_speed", "wind_kph", "wind_mph", "wind_mps"]
            )
        ),
        "rainfall": _num(
            _recursive_find(
                report,
                ["rainfall", "precip_mm", "precipitation"]
            )
        ),
        "pressure": _num(
            _recursive_find(
                report,
                ["pressure", "pressure_mb", "pressure_hpa"]
            )
        ),
    }


def _pollutants(report: Dict[str, Any]) -> Dict[str, Optional[float]]:
    return {
        "pm25": _num(
            _recursive_find(report, ["pm25", "pm2_5", "pm2.5"])
        ),
        "pm10": _num(
            _recursive_find(report, ["pm10"])
        ),
        "no2": _num(
            _recursive_find(report, ["no2"])
        ),
        "so2": _num(
            _recursive_find(report, ["so2"])
        ),
        "co": _num(
            _recursive_find(report, ["co"])
        ),
        "o3": _num(
            _recursive_find(report, ["o3"])
        ),
    }


def _aqi(report: Dict[str, Any]) -> Optional[float]:
    return _num(
        _recursive_find(
            report,
            ["indicative_aqi", "aqi", "overall_aqi"]
        )
    )


def _next_pm25(report: Dict[str, Any]) -> Optional[float]:
    return _num(
        _recursive_find(
            report,
            [
                "predicted_pm25_next_1h",
                "next_hour_pm25",
                "pm25_next_hour",
                "predicted_pm25",
            ],
        )
    )


def build_why_engine(report: Dict[str, Any]) -> Dict[str, Any]:
    p = _pollutants(report)
    w = _weather(report)
    next_pm25 = _next_pm25(report)

    reasons = []

    if p["pm25"] is not None:
        if p["pm25"] >= 90:
            reasons.append(
                f"High PM2.5 loading ({p['pm25']:.1f} µg/m³)."
            )
        elif p["pm25"] >= 60:
            reasons.append(
                f"Elevated PM2.5 ({p['pm25']:.1f} µg/m³)."
            )

    if p["pm10"] is not None and p["pm10"] >= 100:
        reasons.append(
            f"Elevated PM10 ({p['pm10']:.1f} µg/m³), indicating particulate loading."
        )

    if p["no2"] is not None and p["no2"] >= 40:
        reasons.append(
            f"Elevated NO₂ ({p['no2']:.1f} µg/m³), consistent with a combustion/traffic indicator."
        )

    if p["co"] is not None and p["co"] >= 1:
        reasons.append(
            f"CO level ({p['co']:.2f}) provides an additional combustion indicator."
        )

    if w["wind_speed"] is not None and w["wind_speed"] < 4:
        reasons.append(
            f"Weak wind dispersion ({w['wind_speed']:.2f}), which can limit pollutant dispersion."
        )

    if w["rainfall"] is not None and w["rainfall"] <= 0:
        reasons.append(
            "No meaningful rainfall is reported, so wet scavenging is limited."
        )

    if next_pm25 is not None and p["pm25"] is not None:
        if next_pm25 > p["pm25"] * 1.10:
            reasons.append(
                f"The model forecast indicates rising PM2.5 toward {next_pm25:.1f} µg/m³."
            )
        elif next_pm25 < p["pm25"] * 0.90:
            reasons.append(
                f"The model forecast indicates falling PM2.5 toward {next_pm25:.1f} µg/m³."
            )

    if not reasons:
        reasons.append(
            "Current pollutant and meteorological signals do not indicate a dominant driver."
        )

    return {
        "summary": " ".join(reasons),
        "reasons": reasons,
        "note": (
            "This is an evidence-based interpretation of available "
            "observations/model outputs, not proof of causality."
        ),
    }


def build_source_indicators(report: Dict[str, Any]) -> Dict[str, Any]:
    p = _pollutants(report)
    w = _weather(report)

    indicators = []

    if p["pm10"] is not None:
        score = min(max(p["pm10"] / 150.0, 0), 1)
        indicators.append({
            "source": "Particulate / road-dust indicator",
            "score": round(score, 3),
        })

    if p["no2"] is not None:
        score = min(max(p["no2"] / 120.0, 0), 1)
        indicators.append({
            "source": "Traffic / combustion indicator",
            "score": round(score, 3),
        })

    if p["co"] is not None:
        score = min(max(p["co"] / 3.0, 0), 1)
        indicators.append({
            "source": "Combustion indicator",
            "score": round(score, 3),
        })

    if p["so2"] is not None:
        score = min(max(p["so2"] / 120.0, 0), 1)
        indicators.append({
            "source": "Industrial / sulfur-bearing emission indicator",
            "score": round(score, 3),
        })

    if w["wind_speed"] is not None:
        score = max(0.0, min((4.0 - w["wind_speed"]) / 4.0, 1.0))
        indicators.append({
            "source": "Meteorological stagnation",
            "score": round(score, 3),
        })

    indicators.sort(key=lambda x: x["score"], reverse=True)

    return {
        "indicators": indicators,
        "note": (
            "Source indicators are statistical/environmental signals and "
            "are not definitive chemical source apportionment."
        ),
    }


def build_policy_actions(report: Dict[str, Any]) -> Dict[str, Any]:
    p = _pollutants(report)
    aqi = _aqi(report)
    sources = build_source_indicators(report)["indicators"]

    labels = " ".join(x["source"].lower() for x in sources)
    actions = []

    if "road-dust" in labels or "road" in labels or (
        p["pm10"] is not None and p["pm10"] >= 100
    ):
        actions.append({
            "priority": "HIGH",
            "action": "Increase road-dust suppression and inspect visibly dusty corridors.",
            "target": "PM10 / PM2.5",
        })

    if "traffic" in labels or "combustion" in labels or (
        p["no2"] is not None and p["no2"] >= 60
    ):
        actions.append({
            "priority": "HIGH",
            "action": "Target congestion corridors, idling and traffic-emission hotspots.",
            "target": "NO2 / PM2.5",
        })

    if "industrial" in labels or (
        p["so2"] is not None and p["so2"] >= 40
    ):
        actions.append({
            "priority": "HIGH",
            "action": "Prioritize industrial-emission inspection and compliance checks.",
            "target": "SO2 / PM2.5",
        })

    if p["pm25"] is not None and p["pm25"] >= 60:
        actions.append({
            "priority": "HIGH",
            "action": "Increase monitoring frequency and public exposure-reduction messaging.",
            "target": "PM2.5",
        })

    if aqi is not None and aqi >= 200:
        actions.append({
            "priority": "HIGH",
            "action": "Escalate short-duration high-pollution response and enforcement.",
            "target": "Multiple pollutants",
        })

    if not actions:
        actions.append({
            "priority": "MEDIUM",
            "action": "Maintain monitoring and observe the forecast trend.",
            "target": "Ambient air quality",
        })

    return {
        "actions": actions,
        "note": (
            "Actions are linked to observed conditions and policy knowledge. "
            "They are recommendations, not causal impact estimates."
        ),
    }


INTERVENTIONS = {
    "road_dust_control": ("Road-dust suppression", 0.04, 0.12),
    "construction_dust_control": ("Construction/demolition dust control", 0.03, 0.10),
    "traffic_management": ("Traffic/emission management", 0.03, 0.09),
    "waste_burning_control": ("Open/waste-burning control", 0.05, 0.15),
    "industrial_emission_control": ("Industrial emission control", 0.04, 0.12),
    "increased_monitoring": ("Increased monitoring/enforcement", 0.00, 0.03),
}


def simulate_interventions(
    baseline_pm25: float,
    selected: list[str],
) -> Dict[str, Any]:
    baseline = _num(baseline_pm25)

    if baseline is None:
        return {
            "available": False,
            "note": "PM2.5 baseline is unavailable."
        }

    low = 0.0
    high = 0.0

    valid = []

    for key in selected:
        if key in INTERVENTIONS:
            valid.append(key)
            _, lo, hi = INTERVENTIONS[key]
            low += lo
            high += hi

    low = min(low, 0.30)
    high = min(high, 0.45)

    estimated_low = max(0.0, baseline * (1 - high))
    estimated_high = max(0.0, baseline * (1 - low))

    return {
        "available": True,
        "baseline_pm25": round(baseline, 2),
        "selected_interventions": valid,
        "reduction_low_pct": round(low * 100, 1),
        "reduction_high_pct": round(high * 100, 1),
        "estimated_pm25_low": round(estimated_low, 2),
        "estimated_pm25_high": round(estimated_high, 2),
        "confidence": "Moderate" if len(valid) <= 1 else "Moderate-Low",
        "methodology": (
            "Heuristic scenario range based on conservative assumptions. "
            "It is not a causal estimate or validated policy counterfactual."
        ),
    }


def build_innovation_report(
    report: Dict[str, Any],
    location: Optional[str] = None,
) -> Dict[str, Any]:

    p = _pollutants(report)
    baseline = p["pm25"]

    source = build_source_indicators(report)

    scenarios = []

    source_text = " ".join(
        item["source"].lower()
        for item in source["indicators"]
    )

    if "road" in source_text:
        scenarios.append("road_dust_control")

    if "traffic" in source_text or "combustion" in source_text:
        scenarios.append("traffic_management")

    if "industrial" in source_text:
        scenarios.append("industrial_emission_control")

    if not scenarios:
        scenarios.append("increased_monitoring")

    simulator = simulate_interventions(
        baseline,
        scenarios[:3],
    )

    return {
        "location": location or _recursive_find(
            report,
            ["location", "city", "place"]
        ),
        "why_engine": build_why_engine(report),
        "source_indicators": source,
        "policy_to_action": build_policy_actions(report),
        "intervention_simulator": simulator,
        "scope": "Location-agnostic; works with WeatherAPI-resolved locations.",
    }
