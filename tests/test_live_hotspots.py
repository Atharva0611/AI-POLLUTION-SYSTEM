from backend.services.live_hotspots import _distance_km, _severity


def test_distance_between_same_point_is_zero():
    assert _distance_km(18.52, 73.85, 18.52, 73.85) == 0


def test_distance_detects_distinct_locations():
    assert _distance_km(18.52, 73.85, 18.50, 73.94) > 5


def test_numeric_us_aqi_severity_boundaries():
    assert _severity(25, "US AQI") == "good"
    assert _severity(75, "US AQI") == "moderate"
    assert _severity(125, "US AQI") == "unhealthy_sensitive"
    assert _severity(250, "US AQI") == "very_unhealthy"
    assert _severity(None, "US AQI") == "unavailable"


def test_weatherapi_index_is_not_treated_as_numeric_us_aqi():
    assert _severity(1, "US EPA index (1-6)") == "good"
    assert _severity(6, "US EPA index (1-6)") == "hazardous"
    assert _severity(None, None) == "unavailable"
