from datetime import datetime, timezone, timedelta

from backend.services.openweather_service import classify_provider_time


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
