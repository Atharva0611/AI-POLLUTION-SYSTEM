from backend.agents.final_agent import final_node


def test_weather_report_uses_aqi_metadata_and_controlling_pollutant():
    state = {
        "route": "weather",
        "environment": {
            "status": "ok",
            "location": {
                "requested_location": "Wagholi",
                "display_name": "Wagholi",
                "region": "Maharashtra",
                "latitude": 18.58,
                "longitude": 73.98,
                "timezone": "Asia/Kolkata",
                "local_time": "2026-10-16 20:30",
            },
            "current": {
                "o3": 81.0,
                "pm2_5": 34.3,
            },
            "current_aqi": {
                "value": 81,
                "category": "Satisfactory",
                "controlling_pollutant": "O3",
                "pollutant": "O3",
                "basis": "Test basis: overall AQI controlled by O3.",
            },
            "prediction": {
                "pm25_next_1h": 36.0,
                "label": "Likely stable",
                "source": "Weather-adjusted PM2.5 estimate",
            },
            "forecast_24_hours": [],
            "policy": [],
            "recommendations": [],
            "data_provenance": {},
        },
    }

    result = final_node(state)
    report = result["final_answer"]

    assert "Controlling pollutant: O3" in report
    assert "AQI basis: Test basis: overall AQI controlled by O3." in report
    assert "not an official CPCB station AQI" in report
    assert "Indicative PM2.5-to-AQI mapping" not in report
