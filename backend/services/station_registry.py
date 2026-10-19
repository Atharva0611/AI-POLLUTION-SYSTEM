"""
CPCB Station Registry & Dynamic Station Discovery Engine
========================================================
Provides dynamic station discovery, data-quality auditing, and distance calculation.
Handles:
  CASE A — Location has its own CPCB monitoring station (within direct_threshold_km, default 3.0 km)
  CASE B — Location has no CPCB station but has suitable nearby stations within search radius (default 50.0 km)
  CASE C — Location has insufficient nearby data (nearest station exceeds radius, forecast suppressed)

Does not hardcode any location to a predetermined station.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "data" / "processed" / "cpcb_station_registry.json"

_CACHED_REGISTRY: Optional[Dict[str, Dict[str, Any]]] = None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance in kilometers between two points
    on the Earth using the Haversine formula.
    """
    radius = 6371.0  # Earth radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(radius * c, 3)


def get_station_registry() -> Dict[str, Dict[str, Any]]:
    """
    Load and return the verified CPCB station registry.
    """
    global _CACHED_REGISTRY
    if _CACHED_REGISTRY is not None:
        return _CACHED_REGISTRY

    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            _CACHED_REGISTRY = json.load(f)
            return _CACHED_REGISTRY

    # Built-in fallback registry for verified monitoring stations
    _CACHED_REGISTRY = {
        "Alandi, Pune - IITM": {
            "station_id": "site_5405",
            "station_name": "Alandi, Pune - IITM",
            "clean_name": "Alandi",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.677245,
            "longitude": 73.898113,
            "total_observations": 9444,
            "start_timestamp": "2024-01-01 00:00:00+00:00",
            "latest_timestamp": "2025-01-28 11:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.85,
            "is_active": True,
        },
        "Hadapsar, Pune - IITM": {
            "station_id": "site_5407",
            "station_name": "Hadapsar, Pune - IITM",
            "clean_name": "Hadapsar",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.500774,
            "longitude": 73.937915,
            "total_observations": 14174,
            "start_timestamp": "2024-05-20 10:00:00+00:00",
            "latest_timestamp": "2025-12-31 23:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.90,
            "is_active": True,
        },
        "Karve Road, Pune - MPCB": {
            "station_id": "site_292",
            "station_name": "Karve Road, Pune - MPCB",
            "clean_name": "Karve Road",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.488664,
            "longitude": 73.814088,
            "total_observations": 12214,
            "start_timestamp": "2024-01-01 00:00:00+00:00",
            "latest_timestamp": "2025-05-23 21:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.88,
            "is_active": True,
        },
        "Mhada Colony, Pune - IITM": {
            "station_id": "site_5404",
            "station_name": "Mhada Colony, Pune - IITM",
            "clean_name": "Mhada Colony",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.552800,
            "longitude": 73.940000,
            "total_observations": 17544,
            "start_timestamp": "2024-01-01 00:00:00+00:00",
            "latest_timestamp": "2025-12-31 23:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.92,
            "is_active": True,
        },
        "Panchawati_Pashan, Pune - IITM": {
            "station_id": "site_5996",
            "station_name": "Panchawati_Pashan, Pune - IITM",
            "clean_name": "Panchawati Pashan",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.530614,
            "longitude": 73.812351,
            "total_observations": 12750,
            "start_timestamp": "2024-01-01 00:00:00+00:00",
            "latest_timestamp": "2025-12-31 23:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.89,
            "is_active": True,
        },
        "Revenue Colony-Shivajinagar, Pune - IITM": {
            "station_id": "site_5409",
            "station_name": "Revenue Colony-Shivajinagar, Pune - IITM",
            "clean_name": "Shivajinagar",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.529557,
            "longitude": 73.849141,
            "total_observations": 17536,
            "start_timestamp": "2024-01-01 08:30:00+00:00",
            "latest_timestamp": "2025-12-31 23:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.91,
            "is_active": True,
        },
        "Savitribai Phule Pune University, Pune - MPCB": {
            "station_id": "site_5767",
            "station_name": "Savitribai Phule Pune University, Pune - MPCB",
            "clean_name": "SPPU",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.552844,
            "longitude": 73.826644,
            "total_observations": 17544,
            "start_timestamp": "2024-01-01 00:00:00+00:00",
            "latest_timestamp": "2025-12-31 23:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.93,
            "is_active": True,
        },
        "Transport Nagar-Nigdi, Pune - IITM": {
            "station_id": "site_5408",
            "station_name": "Transport Nagar-Nigdi, Pune - IITM",
            "clean_name": "Nigdi",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.663927,
            "longitude": 73.767650,
            "total_observations": 17544,
            "start_timestamp": "2024-01-01 00:00:00+00:00",
            "latest_timestamp": "2025-12-31 23:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.90,
            "is_active": True,
        },
        "Katraj Dairy, Pune - MPCB": {
            "station_id": "site_5766",
            "station_name": "Katraj Dairy, Pune - MPCB",
            "clean_name": "Katraj Dairy",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.501805,
            "longitude": 73.809360,
            "total_observations": 17544,
            "start_timestamp": "2024-01-01 00:00:00+00:00",
            "latest_timestamp": "2025-12-31 23:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.92,
            "is_active": True,
        },
        "Bhumkar Nagar, Pune - IITM": {
            "station_id": "site_5988",
            "station_name": "Bhumkar Nagar, Pune - IITM",
            "clean_name": "Bhumkar Nagar",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.603027,
            "longitude": 73.749413,
            "total_observations": 14147,
            "start_timestamp": "2024-01-01 00:00:00+00:00",
            "latest_timestamp": "2025-12-31 23:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.91,
            "is_active": True,
        },
        "Dhankawadi, Pune - IITM": {
            "station_id": "site_6012",
            "station_name": "Dhankawadi, Pune - IITM",
            "clean_name": "Dhankawadi",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.465420,
            "longitude": 73.850152,
            "total_observations": 8399,
            "start_timestamp": "2025-01-15 11:15:00+00:00",
            "latest_timestamp": "2025-12-31 09:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.84,
            "is_active": True,
        },
        "Bhosari, Pune - IITM": {
            "station_id": "site_5406",
            "station_name": "Bhosari, Pune - IITM",
            "clean_name": "Bhosari",
            "city": "Pune",
            "state": "Maharashtra",
            "latitude": 18.621009,
            "longitude": 73.850130,
            "total_observations": 17077,
            "start_timestamp": "2024-01-01 00:00:00+00:00",
            "latest_timestamp": "2025-12-12 12:00:00+00:00",
            "pollutants_available": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"],
            "data_quality_score": 0.89,
            "is_active": True,
        },
    }
    return _CACHED_REGISTRY


def discover_cpcb_stations(
    latitude: float,
    longitude: float,
    max_radius_km: float = 50.0,
    direct_threshold_km: float = 3.0,
    required_pollutants: Optional[List[str]] = None,
    max_observation_age_hours: float = 72.0,
) -> Dict[str, Any]:
    """
    Dynamically discover, audit, and rank CPCB monitoring stations
    relative to target coordinates.

    Returns a structured audit categorizing the location into:
      CASE_A: Direct station match (distance <= direct_threshold_km)
      CASE_B: Spatially eligible stations within max_radius_km
      CASE_C: Insufficient CPCB data (no stations within max_radius_km)
    """
    registry = get_station_registry()
    if required_pollutants is None:
        required_pollutants = ["PM2.5"]

    def _norm_pol(p: str) -> str:
        return str(p).replace(".", "").replace("_", "").upper()

    required_set = {_norm_pol(p) for p in required_pollutants}

    ranked_stations: List[Dict[str, Any]] = []
    stale_stations: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for name, st in registry.items():
        if not st.get("is_active", True):
            continue

        st_lat = float(st["latitude"])
        st_lon = float(st["longitude"])
        dist_km = haversine_distance(latitude, longitude, st_lat, st_lon)

        avail = {_norm_pol(p) for p in st.get("pollutants_available", [])}
        has_required = required_set.issubset(avail)
        quality_score = float(st.get("data_quality_score", 0.5))

        # Suitability score penalizes distance and rewards data completeness
        # suitability = quality_score / (1.0 + 0.05 * dist_km)
        suitability = round(quality_score / (1.0 + 0.05 * dist_km), 4)

        timestamp_text = st.get("latest_timestamp")
        observation_age_hours = None
        fresh = False

        if timestamp_text:
            try:
                observed_at = datetime.fromisoformat(
                    str(timestamp_text).replace("Z", "+00:00")
                )
                if observed_at.tzinfo is None:
                    observed_at = observed_at.replace(tzinfo=timezone.utc)
                observation_age_hours = (
                    now - observed_at.astimezone(timezone.utc)
                ).total_seconds() / 3600.0
                fresh = 0 <= observation_age_hours <= max_observation_age_hours
            except (TypeError, ValueError):
                pass

        station_entry = {
            "station_id": st.get("station_id"),
            "station_name": st["station_name"],
            "clean_name": st.get("clean_name", st["station_name"]),
            "city": st.get("city", "Unknown"),
            "state": st.get("state", "Unknown"),
            "latitude": st_lat,
            "longitude": st_lon,
            "distance_km": dist_km,
            "has_required_pollutants": has_required,
            "pollutants_available": st.get("pollutants_available", []),
            "total_observations": st.get("total_observations", 0),
            "latest_timestamp": timestamp_text,
            "observation_age_hours": observation_age_hours,
            "data_quality_score": quality_score,
            "suitability_score": suitability,
        }

        if fresh:
            ranked_stations.append(station_entry)
        else:
            stale_stations.append(station_entry)

    # Sort strictly by distance first, then suitability
    ranked_stations.sort(key=lambda s: (s["distance_km"], -s["suitability_score"]))

    if not ranked_stations:
        # Only classify the failure as stale observations when a stale station
        # is geographically within the requested search radius.
        stale_within_radius = [
            station for station in stale_stations
            if station["distance_km"] <= max_radius_km
            and station["has_required_pollutants"]
        ]
        nearest_stale = (
            min(stale_within_radius, key=lambda station: station["distance_km"])
            if stale_within_radius else None
        )

        if nearest_stale is not None:
            message = (
                f"No CPCB station has an observation within "
                f"{max_observation_age_hours:g} hours (search radius: "
                f"{max_radius_km:g} km). "
                f"Nearest stale station: '{nearest_stale['clean_name']}', "
                f"last observation: {nearest_stale['latest_timestamp']}. "
                "Forecast suppressed because the 72-hour freshness requirement "
                "is enforced."
            )
            case_description = "STALE_OBSERVATIONS"
        else:
            nearest_any = min(
                (
                    station for station in stale_stations
                    if station["has_required_pollutants"]
                ),
                key=lambda station: station["distance_km"],
                default=None,
            )
            if nearest_any is None:
                message = "No active CPCB monitoring station with the required pollutants was found."
            else:
                message = (
                    f"No verified CPCB monitoring station exists within "
                    f"{max_radius_km:g} km search radius. The nearest station is "
                    f"'{nearest_any['clean_name']}' at "
                    f"{nearest_any['distance_km']:.1f} km; its latest observation "
                    f"is {nearest_any['latest_timestamp']}. "
                    "A numerical forecast is suppressed."
                )
            nearest_stale = nearest_any
            case_description = "INSUFFICIENT_LOCAL_DATA"

        return {
            "case": "CASE_C",
            "case_description": case_description,
            "target_coordinates": {"latitude": latitude, "longitude": longitude},
            "primary_station": None,
            "eligible_stations": [],
            "nearest_station_outside_radius": nearest_stale,
            "max_radius_km": max_radius_km,
            "message": message,
        }

    nearest = ranked_stations[0]

    # Filter eligible stations within radius having required pollutants
    within_radius = [
        s for s in ranked_stations
        if s["distance_km"] <= max_radius_km and s["has_required_pollutants"]
    ]

    # CASE A: Target location is within direct station threshold (<= 3.0 km)
    if nearest["distance_km"] <= direct_threshold_km and nearest["has_required_pollutants"]:
        return {
            "case": "CASE_A",
            "case_description": "DIRECT_STATION_MATCH",
            "target_coordinates": {"latitude": latitude, "longitude": longitude},
            "primary_station": nearest,
            "eligible_stations": [nearest],
            "nearest_station_outside_radius": None,
            "max_radius_km": max_radius_km,
            "direct_threshold_km": direct_threshold_km,
            "message": (
                f"Location is within {nearest['distance_km']:.2f} km of official "
                f"CPCB station '{nearest['clean_name']}'. Direct station forecast applies."
            ),
        }

    # CASE B: No direct station, but suitable nearby stations exist within max_radius_km
    if within_radius:
        # Compute inverse distance weights (IDW) for spatial interpolation
        # w_i = (1 / d_i^2) / sum(1 / d_j^2)
        power = 2.0
        raw_weights = [1.0 / (s["distance_km"] ** power) for s in within_radius]
        sum_w = sum(raw_weights)
        for s, rw in zip(within_radius, raw_weights):
            s["spatial_weight"] = round(rw / sum_w, 4) if sum_w > 0 else 0.0

        return {
            "case": "CASE_B",
            "case_description": "SPATIAL_ESTIMATION_ELIGIBLE",
            "target_coordinates": {"latitude": latitude, "longitude": longitude},
            "primary_station": within_radius[0],
            "eligible_stations": within_radius[:4],  # Top contributing stations
            "nearest_station_outside_radius": None,
            "max_radius_km": max_radius_km,
            "direct_threshold_km": direct_threshold_km,
            "message": (
                f"Location has no direct CPCB monitor. Found {len(within_radius)} "
                f"active station(s) within {max_radius_km} km. "
                f"Nearest is '{within_radius[0]['clean_name']}' at {within_radius[0]['distance_km']:.2f} km. "
                "Spatial estimation applied."
            ),
        }

    # CASE C: Nearest station exceeds search radius — insufficient local CPCB data
    return {
        "case": "CASE_C",
        "case_description": "INSUFFICIENT_LOCAL_DATA",
        "target_coordinates": {"latitude": latitude, "longitude": longitude},
        "primary_station": None,
        "eligible_stations": [],
        "nearest_station_outside_radius": nearest,
        "max_radius_km": max_radius_km,
        "direct_threshold_km": direct_threshold_km,
        "message": (
            f"No CPCB monitoring station found within {max_radius_km} km radius. "
            f"Nearest station is '{nearest['clean_name']}' ({nearest['city']}, {nearest['state']}) "
            f"located at {nearest['distance_km']:.1f} km away. "
            "Reliable CPCB ML forecasting is unavailable for this location to avoid misleading extrapolation."
        ),
    }
