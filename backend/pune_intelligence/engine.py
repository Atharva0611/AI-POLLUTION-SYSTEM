import math

def _num(v):
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return None if math.isnan(x) or math.isinf(x) else x
    except (TypeError, ValueError):
        return None

def _find(data, aliases):
    if isinstance(data, dict):
        for k, v in data.items():
            nk = str(k).lower().replace(".", "").replace("-", "_").replace(" ", "_")
            if nk in aliases:
                return v
        for v in data.values():
            x = _find(v, aliases)
            if x is not None:
                return x
    elif isinstance(data, list):
        for v in data:
            x = _find(v, aliases)
            if x is not None:
                return x
    return None

def pollutant(report, name):
    groups = {
        "pm25": {"pm25", "pm2_5", "pm25_current", "current_pm25"},
        "pm10": {"pm10", "pm10_current"},
        "no2": {"no2"},
        "so2": {"so2"},
        "co": {"co"},
        "o3": {"o3"},
    }
    return _num(_find(report, groups.get(name, {name})))

def weather(report, name):
    groups = {
        "wind_speed": {"wind_speed", "wind_kph", "wind_mph", "wind_mps"},
        "rainfall": {"rainfall", "precip_mm", "precipitation", "rain_mm"},
        "temperature": {"temperature", "temp_c", "temp"},
        "humidity": {"humidity"},
    }
    return _num(_find(report, groups.get(name, {name})))

def next_pm25(report):
    return _num(_find(report, {
        "predicted_pm25_next_1h", "next_hour_pm25", "pm25_next_hour", "predicted_pm25"
    }))

def _score(v, cuts):
    if v is None:
        return 0.0
    if v <= cuts[0]:
        return 0.0
    for i in range(1, len(cuts)):
        lo, hi = cuts[i-1], cuts[i]
        if v <= hi:
            return ((v-lo)/max(hi-lo, 1e-9)) * (i/(len(cuts)-1)) * 100.0
    return 100.0

def factor_scores(report):
    pm25, pm10 = pollutant(report, "pm25"), pollutant(report, "pm10")
    no2, so2, co = pollutant(report, "no2"), pollutant(report, "so2"), pollutant(report, "co")
    wind, rain = weather(report, "wind_speed"), weather(report, "rainfall")

    dust = max(_score(pm10, [50,100,150,250]), _score(pm25, [30,60,90,120]))
    traffic = max(_score(no2, [40,80,180,280]), _score(co, [1000,2000,5000,10000]))
    industry = _score(so2, [40,80,180,380])
    stagnation = 0.0 if wind is None else max(0.0, min((4-wind)/4*100, 100))
    rain_scavenging = 0.0 if rain is None else max(0.0, min(rain/10*100, 100))

    return {
        "particulate_dust": round(dust, 1),
        "traffic_combustion": round(traffic, 1),
        "industrial_sulfur": round(industry, 1),
        "meteorological_stagnation": round(stagnation, 1),
        "rain_scavenging": round(rain_scavenging, 1),
    }

def environmental_score(report):
    pm25, pm10, no2 = pollutant(report, "pm25"), pollutant(report, "pm10"), pollutant(report, "no2")
    wind, rain = weather(report, "wind_speed"), weather(report, "rainfall")

    c = {
        "pm25": _score(pm25, [30,60,90,120,250]),
        "pm10": _score(pm10, [50,100,150,250,350]),
        "no2": _score(no2, [40,80,180,280,400]),
        "wind_stagnation": 0.0 if wind is None else max(0.0, min((4-wind)/4*100,100)),
    }
    value = c["pm25"]*0.40 + c["pm10"]*0.20 + c["no2"]*0.15 + c["wind_stagnation"]*0.20
    if rain is not None and rain >= 2:
        value -= 10
    value = max(0, min(value, 100))

    band = (
        "Low" if value < 20 else
        "Guarded" if value < 40 else
        "Elevated" if value < 60 else
        "High" if value < 80 else "Critical"
    )
    return {
        "score": round(value, 1),
        "band": band,
        "components": {k: round(v, 1) for k, v in c.items()},
        "note": "Comparative Pune locality score; not official AQI."
    }

def _actions(f):
    a = []
    if f["particulate_dust"] >= 40:
        a.append({"priority":"HIGH","action":"Road-dust suppression and construction-dust compliance checks","targets":["PM10","PM2.5"]})
    if f["traffic_combustion"] >= 40:
        a.append({"priority":"HIGH","action":"Traffic-corridor and idling/emission enforcement","targets":["NO2","PM2.5"]})
    if f["industrial_sulfur"] >= 40:
        a.append({"priority":"HIGH","action":"Industrial-emission inspection and compliance review","targets":["SO2","PM2.5"]})
    if f["meteorological_stagnation"] >= 50:
        a.append({"priority":"MEDIUM","action":"Increase monitoring during weak-dispersion windows","targets":["PM2.5","PM10"]})
    if not a:
        a.append({"priority":"MEDIUM","action":"Maintain monitoring and observe the forecast trend","targets":["Ambient air quality"]})
    return a

def simulate(report, selected=None):
    base = pollutant(report, "pm25")
    if base is None:
        return {"available": False, "reason": "PM2.5 unavailable."}
    f = factor_scores(report)
    if selected is None:
        selected = []
        if f["particulate_dust"] >= 40: selected.append("road_dust_control")
        if f["traffic_combustion"] >= 40: selected.append("traffic_management")
        if f["industrial_sulfur"] >= 40: selected.append("industrial_control")
        if not selected: selected = ["monitoring"]

    effects = {
        "road_dust_control": (0.04,0.12),
        "construction_control": (0.03,0.10),
        "traffic_management": (0.03,0.09),
        "industrial_control": (0.04,0.12),
        "waste_burning_control": (0.05,0.15),
        "monitoring": (0.00,0.03),
    }
    lo = min(sum(effects.get(x,(0,0))[0] for x in selected), 0.30)
    hi = min(sum(effects.get(x,(0,0))[1] for x in selected), 0.45)
    return {
        "available": True,
        "baseline_pm25": round(base,2),
        "selected_interventions": selected,
        "reduction_low_pct": round(lo*100,1),
        "reduction_high_pct": round(hi*100,1),
        "estimated_pm25_low": round(max(0, base*(1-hi)),2),
        "estimated_pm25_high": round(max(0, base*(1-lo)),2),
        "confidence": "Moderate" if len(selected) <= 1 else "Moderate-Low",
        "methodology": "Heuristic scenario range; not a causal policy counterfactual.",
    }

def build_location_intelligence(report, location, representative_station=None):
    factors = factor_scores(report)
    ranked = sorted(factors.items(), key=lambda x: x[1], reverse=True)
    nxt = next_pm25(report)
    cur = pollutant(report, "pm25")

    trend = None
    if cur is not None and nxt is not None:
        d = nxt-cur
        trend = {
            "current_pm25": round(cur,2),
            "next_hour_pm25": round(nxt,2),
            "delta": round(d,2),
            "trend": "Rise" if d >= 2 else "Fall" if d <= -2 else "Stable"
        }

    return {
        "innovation": "Pune Locality Environmental Intelligence",
        "location": location,
        "scope": "100+ Pune locality network",
        "representative_cpcb_station": representative_station,
        "environmental_score": environmental_score(report),
        "factor_fingerprint": {
            "top_factors": [{"factor":k,"score":v} for k,v in ranked if v>0][:6],
            "note": "Indicators, not definitive source apportionment."
        },
        "next_hour_signal": trend or {"available": False},
        "policy_to_action": {
            "actions": _actions(factors),
            "note": "Condition-based action mapping, not causal policy impact."
        },
        "intervention_simulator": simulate(report),
    }
