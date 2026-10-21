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



def test_weatherapi_current_data_is_included_and_timestamp_validated(monkeypatch):
    monkeypatch.setattr(live_environment, "OpenWeatherClient", FakeOpenWeather)
    monkeypatch.setattr(live_environment, "_openaq_result", lambda *args: {
        "status": "no_fresh_data", "provider": "OpenAQ", "stations": [],
        "measurements": [], "live_measurements": [], "fresh_count": 0,
        "error": "No fresh measurements."
    })
    now = datetime.now(timezone.utc).timestamp()
    monkeypatch.setattr(live_environment, "get_weatherapi_current", lambda lat, lon: {
        "source": "WeatherAPI", "pm2_5": 18.5, "pm10": 30.0, "no2": 12.0,
        "so2": 3.0, "co": 250.0, "o3": 40.0, "last_updated": "current",
        "last_updated_epoch": now, "us_epa_index": 2, "uk_defra_index": 2,
    })
    result = live_environment.current_environment("Wagholi, Pune", 15000)
    weatherapi = result["providers"]["weatherapi_air_quality"]
    assert result["status"] == "ok"
    assert weatherapi["status"] == "ok"
    assert weatherapi["provider"] == "WeatherAPI"
    assert weatherapi["pm2_5"] == 18.5
    assert weatherapi["is_current"] is True


def test_weatherapi_stale_observation_is_not_marked_current(monkeypatch):
    now = datetime.now(timezone.utc).timestamp()
    result = live_environment._validated_weatherapi({
        "source": "WeatherAPI", "pm2_5": 18.5,
        "last_updated": "old", "last_updated_epoch": now - 6 * 60 * 60,
    }, max_age=180)
    assert result["status"] == "stale_or_invalid"
    assert result["is_current"] is False
