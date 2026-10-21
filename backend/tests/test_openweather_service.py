from datetime import datetime, timezone, timedelta

from backend.services.openweather_service import OpenWeatherClient, OpenWeatherError, classify_provider_time


class FakeResponse:
    status_code = 200
    def __init__(self, payload):
        self.payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []
    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.payloads.pop(0))


def test_openweather_timestamp_inside_live_window_is_current():
    now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
    stamp = (now - timedelta(minutes=90)).timestamp()
    result = classify_provider_time(stamp, 180, now)
    assert result["is_current"] is True
    assert result["freshness"] == "fresh"
    assert result["age_minutes"] == 90


def test_openweather_stale_missing_invalid_and_future_are_not_current():
    now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
    assert classify_provider_time((now - timedelta(minutes=181)).timestamp(), 180, now)["is_current"] is False
    assert classify_provider_time(None, 180, now)["freshness"] == "missing_timestamp"
    assert classify_provider_time("bad-time", 180, now)["freshness"] == "invalid_timestamp"
    assert classify_provider_time((now + timedelta(minutes=1)).timestamp(), 180, now)["is_current"] is False


def test_openweather_pollution_parses_native_aqi_scale_and_components():
    stamp = 1792584000
    client = OpenWeatherClient(api_key="test-only", session=FakeSession([{
        "list": [{"dt": stamp, "main": {"aqi": 3}, "components": {"pm2_5": 12.5, "pm10": 19.0, "no2": 4.0}}]
    }]))
    result = client.current_air_pollution(18.5, 73.8)
    assert result["aqi"] == 3
    assert result["aqi_scale"] == "OpenWeather 1-5"
    assert result["components"]["pm2_5"] == 12.5
    assert result["observed_at_unix"] == stamp


def test_openweather_weather_parses_current_conditions():
    stamp = 1792584000
    client = OpenWeatherClient(api_key="test-only", session=FakeSession([{
        "dt": stamp, "main": {"temp": 25, "feels_like": 26, "humidity": 45, "pressure": 1008},
        "wind": {"speed": 2.5, "deg": 90}, "clouds": {"all": 20},
        "weather": [{"description": "clear sky"}]
    }]))
    result = client.current_weather(18.5, 73.8)
    assert result["temperature_c"] == 25
    assert result["humidity_percent"] == 45
    assert result["wind_speed_m_s"] == 2.5
    assert result["condition"] == "clear sky"


def test_openweather_requires_key_without_leaking_credentials():
    client = OpenWeatherClient(api_key="")
    try:
        client.current_weather(18.5, 73.8)
    except OpenWeatherError as exc:
        assert "OPENWEATHER_API_KEY" in str(exc)
        assert "test-only" not in str(exc)
    else:
        raise AssertionError("Missing key should raise a provider configuration error")
