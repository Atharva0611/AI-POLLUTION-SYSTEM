from datetime import datetime, timezone

from backend.services.openaq_service import classify_freshness


def test_measurement_within_configured_live_window_is_fresh(monkeypatch):
    monkeypatch.setenv("OPENAQ_LIVE_MAX_AGE_MINUTES", "180")
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    result = classify_freshness("2026-10-20T10:00:00Z", now)
    assert result["freshness"] == "fresh"
    assert result["is_fresh"] is True
    assert result["age_minutes"] == 120


def test_measurement_outside_live_window_is_not_fresh(monkeypatch):
    monkeypatch.setenv("OPENAQ_LIVE_MAX_AGE_MINUTES", "180")
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    result = classify_freshness("2026-10-20T08:59:00Z", now)
    assert result["freshness"] == "delayed"
    assert result["is_fresh"] is False


def test_missing_and_invalid_timestamps_are_not_fresh():
    assert classify_freshness(None)["is_fresh"] is False
    assert classify_freshness("not-a-date")["freshness"] == "invalid_timestamp"


def test_future_timestamps_are_not_fresh():
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    for timestamp in ("2026-10-21T12:00:00Z", "2026-10-20T12:30:00Z"):
        result = classify_freshness(timestamp, now)
        assert result["freshness"] == "future_timestamp"
        assert result["is_fresh"] is False
