from backend.innovation.engine import build_innovation_report, simulate_interventions


def test_simulator():
    out = simulate_interventions(100, ["road_dust_control"])
    assert out["baseline_pm25"] == 100
    assert out["estimated_pm25_low"] < 100
    assert out["estimated_pm25_high"] < 100


def test_build_report_without_optional_modules():
    report = {
        "location": "Alandi",
        "current": {
            "temperature": 26,
            "humidity": 70,
            "wind_speed": 1.0,
            "rainfall": 0,
        },
        "air_quality": {
            "pm25": 85,
            "pm10": 120,
            "no2": 90,
            "co": 1.4,
            "so2": 20,
            "o3": 40,
            "indicative_aqi": 160,
        },
        "xgb": {"predicted_pm25_next_1h": 95},
    }
    out = build_innovation_report(report)
    assert out["location"] == "Alandi"
    assert out["why_engine"]["summary"]
    assert out["source_indicators"]["indicators"]
    assert out["policy_to_action"]["actions"]
    assert out["intervention_simulator"]["available"] is True
