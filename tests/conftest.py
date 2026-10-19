import copy
from datetime import datetime, timezone

import pytest

from backend.services import station_registry


@pytest.fixture
def fresh_station_data(monkeypatch):
    """Simulate fresh registry metadata for forecast integration tests only."""
    original = station_registry.get_station_registry()
    simulated = copy.deepcopy(original)
    now = datetime.now(timezone.utc).isoformat()

    for station in simulated.values():
        if station.get("is_active", True):
            station["latest_timestamp"] = now

    monkeypatch.setattr(
        station_registry,
        "get_station_registry",
        lambda: simulated,
    )
    return simulated
