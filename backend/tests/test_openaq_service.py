from datetime import datetime, timezone

from backend.services.openaq_service import classify_freshness


def test_fresh_timestamp_is_classified_fresh():
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    result = classify_freshness("2026-10-20T01:00:00Z", now)
    assert result["freshness"] == "fresh"
    assert result["is_fresh"] is True
    assert result["age_hours"] == 11


def test_old_timestamp_is_stale():
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    result = classify_freshness("2026-10-15T08:45:00Z", now)
    assert result["freshness"] == "stale"
    assert result["is_fresh"] is False


def test_missing_and_invalid_timestamps_are_not_fresh():
    assert classify_freshness(None)["is_fresh"] is False
    assert classify_freshness("not-a-date")["freshness"] == "invalid_timestamp"


def test_future_timestamp_is_not_fresh():
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    result = classify_freshness("2026-10-21T12:00:00Z", now)
    assert result["freshness"] == "future_timestamp"
    assert result["is_fresh"] is False
