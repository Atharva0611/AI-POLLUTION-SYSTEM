"""
Universal Location Resolver
===========================
Resolves any Indian location input (city, district, town, village, locality,
or direct latitude/longitude coordinates) into validated geographical coordinates.

Maintains independent storage of the user-selected location and its coordinates,
ensuring the system never silently replaces the user's location with a nearby station.
"""

from __future__ import annotations

import os
import re
import requests
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from dotenv import load_dotenv
from backend.services.station_registry import discover_cpcb_stations

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AI-Pollution-System/2.0"

# Local cache of known location coordinates to minimize external latency
LOCAL_COORDINATE_REGISTRY: Dict[str, Tuple[float, float, str]] = {
    # Pune Metropolitan Localities
    "pune": (18.5204, 73.8567, "Pune, Maharashtra, India"),
    "alandi": (18.6772, 73.8981, "Alandi, Pune, Maharashtra, India"),
    "wagholi": (18.5790, 73.9830, "Wagholi, Pune, Maharashtra, India"),
    "hadapsar": (18.5008, 73.9379, "Hadapsar, Pune, Maharashtra, India"),
    "karve road": (18.4887, 73.8141, "Karve Road, Pune, Maharashtra, India"),
    "karve nagar": (18.4887, 73.8141, "Karve Nagar, Pune, Maharashtra, India"),
    "shivajinagar": (18.5296, 73.8491, "Shivajinagar, Pune, Maharashtra, India"),
    "kothrud": (18.5074, 73.8077, "Kothrud, Pune, Maharashtra, India"),
    "baner": (18.5590, 73.7868, "Baner, Pune, Maharashtra, India"),
    "hinjewadi": (18.5913, 73.7389, "Hinjewadi, Pune, Maharashtra, India"),
    "wakad": (18.5987, 73.7688, "Wakad, Pune, Maharashtra, India"),
    "bhosari": (18.6210, 73.8501, "Bhosari, Pune, Maharashtra, India"),
    "bhumkar nagar": (18.6030, 73.7494, "Bhumkar Nagar, Pune, Maharashtra, India"),
    "pashan": (18.5306, 73.8124, "Pashan, Pune, Maharashtra, India"),
    "nigdi": (18.6639, 73.7676, "Nigdi, Pune, Maharashtra, India"),
    "katraj": (18.4529, 73.8652, "Katraj, Pune, Maharashtra, India"),
    "dhankawadi": (18.4654, 73.8502, "Dhankawadi, Pune, Maharashtra, India"),
    "viman nagar": (18.5679, 73.9143, "Viman Nagar, Pune, Maharashtra, India"),
    "kharadi": (18.5516, 73.9349, "Kharadi, Pune, Maharashtra, India"),
    "magarpatta": (18.5143, 73.9281, "Magarpatta, Pune, Maharashtra, India"),
    "kalyani nagar": (18.5463, 73.9033, "Kalyani Nagar, Pune, Maharashtra, India"),
    "chakan": (18.7606, 73.8576, "Chakan, Pune, Maharashtra, India"),
    "akurdi": (18.6496, 73.7707, "Akurdi, Pune, Maharashtra, India"),
    "pimpri": (18.6279, 73.8009, "Pimpri, Pune, Maharashtra, India"),
    "chinchwad": (18.6279, 73.8009, "Chinchwad, Pune, Maharashtra, India"),
    "sppu": (18.5528, 73.8266, "Savitribai Phule Pune University, Pune, Maharashtra, India"),
    
    # Major Indian Cities & Districts
    "mumbai": (18.9750, 72.8258, "Mumbai, Maharashtra, India"),
    "delhi": (28.6139, 77.2090, "New Delhi, Delhi, India"),
    "new delhi": (28.6139, 77.2090, "New Delhi, Delhi, India"),
    "bengaluru": (12.9716, 77.5946, "Bengaluru, Karnataka, India"),
    "bangalore": (12.9716, 77.5946, "Bengaluru, Karnataka, India"),
    "nagpur": (21.1458, 79.0882, "Nagpur, Maharashtra, India"),
    "nashik": (19.9975, 73.7898, "Nashik, Maharashtra, India"),
    "hyderabad": (17.3850, 78.4867, "Hyderabad, Telangana, India"),
    "chennai": (13.0827, 80.2707, "Chennai, Tamil Nadu, India"),
    "kolkata": (22.5726, 88.3639, "Kolkata, West Bengal, India"),
    "beed": (18.9891, 75.7601, "Beed, Maharashtra, India"),
    "aurangabad": (19.8762, 75.3433, "Chhatrapati Sambhajinagar, Maharashtra, India"),
    "solapur": (17.6599, 75.9064, "Solapur, Maharashtra, India"),
    "kolhapur": (16.7050, 74.2433, "Kolhapur, Maharashtra, India"),
    "thane": (19.2183, 72.9781, "Thane, Maharashtra, India"),
    "navi mumbai": (19.0330, 73.0297, "Navi Mumbai, Maharashtra, India"),
}


def parse_coordinate_string(text: str) -> Optional[Tuple[float, float]]:
    """
    Check if the input is a direct coordinate string such as:
    '18.579, 73.983' or 'lat: 18.579, lon: 73.983'
    """
    text = str(text or "").strip()
    match = re.search(r"([-+]?\d{1,2}(?:\.\d+)?)\s*,\s*([-+]?\d{1,3}(?:\.\d+)?)", text)
    if match:
        try:
            lat = float(match.group(1))
            lon = float(match.group(2))
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                return (lat, lon)
        except ValueError:
            pass
    return None


def clean_location_input(text: str) -> str:
    """Normalize input text by stripping conversational prefixes/suffixes."""
    text = str(text or "").strip()
    # Strip common leading question phrases
    patterns = [
        r"^(?:what\s+is\s+the\s+)?(?:air\s+quality|aqi|weather|pollution|forecast)\s+(?:in|of|for|at)\s+",
        r"^(?:current\s+)?(?:pollution|weather|forecast|conditions?)\s+(?:in|of|for|at)\s+",
        r"^(?:predict|forecast)\s+(?:pollution|pm2\.5|pm10|air quality)?\s*(?:in|of|for|at)\s*",
        r"^(?:is|are)\s+",
        r"\s+(?:a\s+pollution\s+hotspot|hotspots?|using\s+xgboost.*|using\s+shap.*|today|now)\??$",
    ]
    for p in patterns:
        text = re.sub(p, "", text, flags=re.IGNORECASE).strip()

    text = re.sub(r"[?!.,;:]+$", "", text).strip()
    return text


def geocode_with_nominatim(location_name: str) -> Optional[Dict[str, Any]]:
    """Query OpenStreetMap Nominatim geocoding service for India."""
    headers = {"User-Agent": USER_AGENT}
    queries = [
        f"{location_name}, Maharashtra, India",
        f"{location_name}, India",
    ]
    for q in queries:
        try:
            resp = requests.get(
                NOMINATIM_URL,
                params={"q": q, "format": "jsonv2", "limit": 1, "countrycodes": "in"},
                headers=headers,
                timeout=5,
            )
            if resp.ok:
                results = resp.json()
                if results and len(results) > 0:
                    item = results[0]
                    return {
                        "latitude": float(item["lat"]),
                        "longitude": float(item["lon"]),
                        "display_name": item.get("display_name", location_name),
                        "source": "nominatim_osm",
                    }
        except Exception:
            continue
    return None


def geocode_with_weatherapi(location_name: str) -> Optional[Dict[str, Any]]:
    """Fallback geocode using WeatherAPI Search endpoint."""
    if not WEATHER_API_KEY:
        return None
    url = "https://api.weatherapi.com/v1/search.json"
    try:
        resp = requests.get(
            url,
            params={"key": WEATHER_API_KEY, "q": location_name},
            timeout=5,
        )
        if resp.ok:
            results = resp.json()
            if results and len(results) > 0:
                item = results[0]
                name = item.get("name", location_name)
                region = item.get("region", "")
                country = item.get("country", "India")
                display = f"{name}, {region}, {country}".replace(", ,", ",")
                return {
                    "latitude": float(item["lat"]),
                    "longitude": float(item["lon"]),
                    "display_name": display,
                    "source": "weatherapi_search",
                }
    except Exception:
        pass
    return None


def resolve_universal_location(
    location_input: Union[str, Dict[str, Any]],
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    max_cpcb_radius_km: float = 50.0,
) -> Dict[str, Any]:
    """
    Primary location-resolution function.
    Accepts place name string, coordinate string, dict with lat/lon, or explicit lat/lon.

    Returns complete metadata separating:
      - user_selected_location (name, coordinates, display_name)
      - cpcb_station_audit (Case A/B/C, eligible stations, distances)
    """
    if latitude is not None and longitude is not None:
        lat = float(latitude)
        lon = float(longitude)
        name = str(location_input or f"Coordinates ({lat:.4f}, {lon:.4f})")
        station_audit = discover_cpcb_stations(lat, lon, max_radius_km=max_cpcb_radius_km)
        return {
            "success": True,
            "location_name": name,
            "display_name": name,
            "latitude": lat,
            "longitude": lon,
            "resolution_source": "explicit_coordinates",
            "cpcb_station_audit": station_audit,
        }
    # 1. Direct coordinate dict input
    if isinstance(location_input, dict):
        lat = location_input.get("latitude") or location_input.get("lat")
        lon = location_input.get("longitude") or location_input.get("lon")
        if lat is not None and lon is not None:
            lat = float(lat)
            lon = float(lon)
            name = location_input.get("name") or f"Coordinates ({lat:.4f}, {lon:.4f})"
            station_audit = discover_cpcb_stations(lat, lon, max_radius_km=max_cpcb_radius_km)
            return {
                "success": True,
                "location_name": name,
                "display_name": name,
                "latitude": lat,
                "longitude": lon,
                "resolution_source": "coordinate_input",
                "cpcb_station_audit": station_audit,
            }

    raw = str(location_input or "").strip()
    if not raw:
        raw = "Pune"

    # 2. Coordinate string check (e.g. "18.579, 73.983")
    coords = parse_coordinate_string(raw)
    if coords:
        lat, lon = coords
        name = f"Coordinates ({lat:.4f}, {lon:.4f})"
        station_audit = discover_cpcb_stations(lat, lon, max_radius_km=max_cpcb_radius_km)
        return {
            "success": True,
            "location_name": name,
            "display_name": name,
            "latitude": lat,
            "longitude": lon,
            "resolution_source": "coordinate_string",
            "cpcb_station_audit": station_audit,
        }

    # 3. Clean location name
    cleaned = clean_location_input(raw)
    low = cleaned.lower()

    # 4. Check local high-precision registry first
    if low in LOCAL_COORDINATE_REGISTRY:
        lat, lon, disp = LOCAL_COORDINATE_REGISTRY[low]
        station_audit = discover_cpcb_stations(lat, lon, max_radius_km=max_cpcb_radius_km)
        return {
            "success": True,
            "location_name": cleaned.title(),
            "display_name": disp,
            "latitude": lat,
            "longitude": lon,
            "resolution_source": "local_coordinate_registry",
            "cpcb_station_audit": station_audit,
        }

    # Also check if any known locality is a substring
    for key, (lat, lon, disp) in sorted(LOCAL_COORDINATE_REGISTRY.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(r"\b" + re.escape(key) + r"\b", low):
            station_audit = discover_cpcb_stations(lat, lon, max_radius_km=max_cpcb_radius_km)
            return {
                "success": True,
                "location_name": key.title(),
                "display_name": disp,
                "latitude": lat,
                "longitude": lon,
                "resolution_source": "local_coordinate_registry_substring",
                "cpcb_station_audit": station_audit,
            }

    # 5. Geocode via Nominatim
    osm_geo = geocode_with_nominatim(cleaned)
    if osm_geo:
        lat = osm_geo["latitude"]
        lon = osm_geo["longitude"]
        station_audit = discover_cpcb_stations(lat, lon, max_radius_km=max_cpcb_radius_km)
        return {
            "success": True,
            "location_name": cleaned.title(),
            "display_name": osm_geo["display_name"],
            "latitude": lat,
            "longitude": lon,
            "resolution_source": "nominatim_osm",
            "cpcb_station_audit": station_audit,
        }

    # 6. Fallback to WeatherAPI search
    w_geo = geocode_with_weatherapi(cleaned)
    if w_geo:
        lat = w_geo["latitude"]
        lon = w_geo["longitude"]
        station_audit = discover_cpcb_stations(lat, lon, max_radius_km=max_cpcb_radius_km)
        return {
            "success": True,
            "location_name": cleaned.title(),
            "display_name": w_geo["display_name"],
            "latitude": lat,
            "longitude": lon,
            "resolution_source": "weatherapi_search",
            "cpcb_station_audit": station_audit,
        }

    # 7. Default fallback with clear flag
    def_lat, def_lon = 18.5204, 73.8567
    station_audit = discover_cpcb_stations(def_lat, def_lon, max_radius_km=max_cpcb_radius_km)
    return {
        "success": False,
        "location_name": cleaned.title(),
        "display_name": f"{cleaned.title()}, India (Approximate)",
        "latitude": def_lat,
        "longitude": def_lon,
        "resolution_source": "fallback_default",
        "cpcb_station_audit": station_audit,
        "warning": f"Geocoding could not pinpoint exact coordinates for '{cleaned}'. Using regional reference.",
    }
