from datetime import datetime, timezone

from backend.api.routes import live_environment
from backend.services.openweather_service import OpenWeatherError


class FakeOpenWeather:
    def __init__(self, *args, **kwargs):
        pass

    def resolve_location(self, location):
        return {
            "requested": location,
            "resolved_name": "Wagholi, Pune, Maharashtra, IN",
            "latitude": 18.58,
            "longitude": 73.98,
            "matches": [],
        }

    def current_air_pollution(self, latitude, longitude):
        return {
            "provider": "OpenWeather",
            "aqi": 2,
            "aqi_scale": "OpenWeather 1-5",
            "components": {"pm2_5": 14.2},
            "observed_at_unix": datetime.now(timezone.utc).timestamp(),
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }

    def current_weather(self, latitude, longitude):
        raise OpenWeatherError("OpenWeather current weather is temporarily unavailable.")


def _fake_openaq(*args):
    return {
        "status": "ok",
        "provider": "OpenAQ",
        "stations": [{"id": 10, "name": "Test station"}],
        "measurements": [],
        "live_measurements": [
            {"pollutant": "pm25", "value": 9.1, "unit": "µg/m³"}
        ],
        "fresh_count": 1,
        "error": None,
    }


def _fake_weatherapi(**overrides):
    result = {
        "weatherapi_name": "Pune",
        "latitude": 18.58,
        "longitude": 73.98,
        "pm2_5": 21.3,
        "pm10": 34.5,
        "no2": 11.0,
        "so2": 4.0,
        "co": 250.0,
        "o3": 30.0,
        "temperature_c": 26.0,
        "humidity": 50,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "last_updated_epoch": int(datetime.now(timezone.utc).timestamp()),
        "source": "WeatherAPI",
        "live": True,
    }
    result.update(overrides)
    return result


def test_partial_provider_failure_keeps_successful_live_sources(monkeypatch):
    monkeypatch.setattr(live_environment, "OpenWeatherClient", FakeOpenWeather)
    monkeypatch.setattr(live_environment, "_openaq_result", _fake_openaq)
    monkeypatch.setattr(
        live_environment, "get_weatherapi_current", lambda lat, lon: _fake_weatherapi()
    )

    result = live_environment.current_environment("Wagholi, Pune", 15000)

    assert result["status"] == "ok"
    assert result["providers"]["openweather_air_pollution"]["status"] == "ok"
    assert result["providers"]["openweather_air_pollution"]["aqi_scale"] == "OpenWeather 1-5"
    assert result["providers"]["openweather_weather"]["status"] == "unavailable"
    assert len(result["providers"]["openaq"]["live_measurements"]) == 1
    assert result["providers"]["weatherapi"]["status"] == "ok"
    assert result["providers"]["weatherapi"]["pm2_5"] == 21.3
    assert result["providers"]["weatherapi"]["source_type"] == "provider_current_air_quality_and_weather"


def test_weatherapi_stale_timestamp_is_not_marked_current(monkeypatch):
    monkeypatch.setattr(live_environment, "OpenWeatherClient", FakeOpenWeather)
    monkeypatch.setattr(
        live_environment,
        "_openaq_result",
        lambda *args: {
            "status": "no_fresh_data",
            "provider": "OpenAQ",
            "stations": [],
            "measurements": [],
            "live_measurements": [],
            "fresh_count": 0,
            "error": "No fresh measurements.",
        },
    )
    monkeypatch.setattr(
        live_environment,
        "get_weatherapi_current",
        lambda lat, lon: _fake_weatherapi(
            last_updated_epoch=int(datetime.now(timezone.utc).timestamp()) - 8 * 60 * 60
        ),
    )

    result = live_environment.current_environment("Wagholi, Pune", 15000)

    assert result["providers"]["weatherapi"]["status"] == "stale_or_invalid"
    assert result["providers"]["weatherapi"]["is_current"] is False
    assert result["status"] == "ok"  # OpenWeather pollution remains current.


def test_weatherapi_failure_does_not_fail_other_providers(monkeypatch):
    class FailingOpenWeather(FakeOpenWeather):
        def current_air_pollution(self, latitude, longitude):
            raise OpenWeatherError("Air pollution provider unavailable.")

        def current_weather(self, latitude, longitude):
            raise OpenWeatherError("Weather provider unavailable.")

    monkeypatch.setattr(live_environment, "OpenWeatherClient", FailingOpenWeather)
    monkeypatch.setattr(
        live_environment,
        "_openaq_result",
        lambda *args: {
            "status": "no_fresh_data",
            "provider": "OpenAQ",
            "stations": [],
            "measurements": [],
            "live_measurements": [],
            "fresh_count": 0,
            "error": "No fresh measurements.",
        },
    )
    monkeypatch.setattr(
        live_environment,
        "get_weatherapi_current",
        lambda lat, lon: (_ for _ in ()).throw(RuntimeError("provider down")),
    )

    result = live_environment.current_environment("Wagholi, Pune", 15000)

    assert result["status"] == "unavailable"
    assert result["providers"]["weatherapi"]["status"] == "unavailable"
    assert "provider down" not in result["providers"]["weatherapi"]["error"]


def test_all_provider_failures_return_unavailable_not_historical_data(monkeypatch):
    class FailingOpenWeather(FakeOpenWeather):
        def current_air_pollution(self, latitude, longitude):
            raise OpenWeatherError("Air pollution provider unavailable.")

        def current_weather(self, latitude, longitude):
            raise OpenWeatherError("Weather provider unavailable.")

    monkeypatch.setattr(live_environment, "OpenWeatherClient", FailingOpenWeather)
    monkeypatch.setattr(
        live_environment,
        "_openaq_result",
        lambda *args: {
            "status": "no_fresh_data",
            "provider": "OpenAQ",
            "stations": [],
            "measurements": [],
            "live_measurements": [],
            "fresh_count": 0,
            "error": "No fresh measurements.",
        },
    )
    monkeypatch.setattr(
        live_environment,
        "get_weatherapi_current",
        lambda lat, lon: (_ for _ in ()).throw(RuntimeError("provider down")),
    )

    result = live_environment.current_environment("Wagholi, Pune", 15000)

    assert result["status"] == "unavailable"
    assert result["providers"]["openweather_air_pollution"]["status"] == "unavailable"
    assert result["providers"]["openweather_weather"]["status"] == "unavailable"
    assert result["providers"]["openaq"]["live_measurements"] == []
    assert result["providers"]["weatherapi"]["status"] == "unavailable"


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
    monkeypatch.setattr(
        universal_location_resolver,
        "resolve_universal_location",
        lambda location: {
            "success": True,
            "display_name": "Wagholi, Pune, Maharashtra, India",
            "latitude": 18.579,
            "longitude": 73.983,
            "resolution_source": "test_registry",
        },
    )
    monkeypatch.setattr(live_environment, "_openaq_result", _fake_openaq)
    monkeypatch.setattr(
        live_environment, "get_weatherapi_current", lambda lat, lon: _fake_weatherapi()
    )

    result = live_environment.current_environment("Wagholi, Pune", 15000)

    assert result["status"] == "ok"
    assert result["location"]["latitude"] == 18.579
    assert result["providers"]["openaq"]["live_measurements"][0]["value"] == 9.1
    assert result["providers"]["weatherapi"]["status"] == "ok"
