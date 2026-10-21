from datetime import datetime, timezone

from backend.api.routes import live_environment
from backend.services.openweather_service import OpenWeatherError


class FakeOpenWeather:
    def __init__(self, *args, **kwargs):
        pass

    def resolve_location(self, location):
        return {"requested": location, "resolved_name": "Wagholi, Pune, Maharashtra, IN",
                "latitude": 18.58, "longitude": 73.98, "matches": []}

    def current_air_pollution(self, latitude, longitude):
        return {"provider": "OpenWeather", "aqi": 2, "aqi_scale": "OpenWeather 1-5",
                "components": {"pm2_5": 14.2}, "observed_at_unix": datetime.now(timezone.utc).timestamp(),
                "observed_at": datetime.now(timezone.utc).isoformat()}

    def current_weather(self, latitude, longitude):
        raise OpenWeatherError("OpenWeather current weather is temporarily unavailable.")


def test_partial_provider_failure_keeps_successful_live_sources(monkeypatch):
    monkeypatch.setattr(live_environment, "OpenWeatherClient", FakeOpenWeather)
    monkeypatch.setattr(live_environment, "_openaq_result", lambda *args: {
        "status": "ok", "provider": "OpenAQ", "stations": [{"id": 10, "name": "Test station"}],
        "measurements": [], "live_measurements": [{"pollutant": "pm25", "value": 9.1, "unit": "µg/m³"}],
        "fresh_count": 1, "error": None
    })
    result = live_environment.current_environment("Wagholi, Pune", 15000)
    assert result["status"] == "ok"
    assert result["providers"]["openweather_air_pollution"]["status"] == "ok"
    assert result["providers"]["openweather_air_pollution"]["aqi_scale"] == "OpenWeather 1-5"
    assert result["providers"]["openweather_weather"]["status"] == "unavailable"
    assert len(result["providers"]["openaq"]["live_measurements"]) == 1


def test_all_provider_failures_return_unavailable_not_historical_data(monkeypatch):
    class FailingOpenWeather(FakeOpenWeather):
        def current_air_pollution(self, latitude, longitude):
            raise OpenWeatherError("Air pollution provider unavailable.")

        def current_weather(self, latitude, longitude):
            raise OpenWeatherError("Weather provider unavailable.")

    monkeypatch.setattr(live_environment, "OpenWeatherClient", FailingOpenWeather)
    monkeypatch.setattr(live_environment, "_openaq_result", lambda *args: {
        "status": "no_fresh_data", "provider": "OpenAQ", "stations": [],
        "measurements": [], "live_measurements": [], "fresh_count": 0,
        "error": "No fresh measurements."
    })
    result = live_environment.current_environment("Wagholi, Pune", 15000)
    assert result["status"] == "unavailable"
    assert result["providers"]["openweather_air_pollution"]["status"] == "unavailable"
    assert result["providers"]["openweather_weather"]["status"] == "unavailable"
    assert result["providers"]["openaq"]["live_measurements"] == []

def test_openaq_remains_available_when_openweather_geocoding_fails(monkeypatch):
    class GeocodingUnavailable(FakeOpenWeather):
        def resolve_location(self, location):
            raise OpenWeatherError("OpenWeather key missing.")

        def current_air_pollution(self, latitude, longitude):
            raise OpenWeatherError("OpenWeather key missing.")

        def current_weather(self, latitude, longitude):
            raise OpenWeatherError("OpenWeather key missing.")

    from backend.services import universal_location_resolver
    monkeypatch.setattr(live_environment, "OpenWeatherClient", GeocodingUnavailable)
    monkeypatch.setattr(universal_location_resolver, "resolve_universal_location", lambda location: {
        "success": True, "display_name": "Wagholi, Pune, Maharashtra, India",
        "latitude": 18.579, "longitude": 73.983, "resolution_source": "test_registry"
    })
    monkeypatch.setattr(live_environment, "_openaq_result", lambda *args: {
        "status": "ok", "provider": "OpenAQ", "stations": [],
        "measurements": [], "live_measurements": [{"pollutant": "pm25", "value": 8.0, "unit": "µg/m³"}],
        "fresh_count": 1, "error": None
    })
    result = live_environment.current_environment("Wagholi, Pune", 15000)
    assert result["status"] == "ok"
    assert result["location"]["latitude"] == 18.579
    assert result["providers"]["openaq"]["live_measurements"][0]["value"] == 8.0
    assert result["providers"]["openweather_air_pollution"]["status"] == "unavailable"
