
"""
Canonical Pune environmental monitoring location registry.

All user-facing location names and station aliases should resolve
through this module before WeatherAPI, CPCB, ML, SHAP or DBSCAN processing.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


PUNE_STATIONS: dict[str, dict[str, Any]] = {

    "Pune": {
        "display_name": "Pune",
        "station_name": None,
        "aliases": [
            "pune",
            "pune city",
            "pune maharashtra",
            "pune city maharashtra",
        ],
        "latitude": 18.5204,
        "longitude": 73.8567,
        "location_type": "city",
    },

    "Alandi": {
        "display_name": "Alandi",
        "station_name": "Alandi, Pune - IITM",
        "aliases": [
            "alandi",
            "alandi pune",
            "alandi iitm",
            "alandi pune iitm",
            "alandi station",
        ],
        "latitude": 18.677245,
        "longitude": 73.898113,
    },

    "Bhosari": {
        "display_name": "Bhosari",
        "station_name": "Bhosari, Pune - IITM",
        "aliases": [
            "bhosari",
            "bhosari pune",
            "bhosari iitm",
            "bhosari pune iitm",
            "bhosari station",
        ],
        "latitude": 18.621009,
        "longitude": 73.850130,
    },

    "Bhumkar Nagar": {
        "display_name": "Bhumkar Nagar",
        "station_name": "Bhumkar Nagar, Pune - IITM",
        "aliases": [
            "bhumkar nagar",
            "bhumkar",
            "bhumkar nagar pune",
            "bhumkar nagar iitm",
            "bhumkar nagar pune iitm",
        ],
        "latitude": 18.603027,
        "longitude": 73.749413,
    },

    "Dhankawadi": {
        "display_name": "Dhankawadi",
        "station_name": "Dhankawadi, Pune - IITM",
        "aliases": [
            "dhankawadi",
            "dhankawadi pune",
            "dhankawadi iitm",
            "dhankawadi pune iitm",
        ],
        "latitude": 18.465420,
        "longitude": 73.850152,
    },

    "Hadapsar": {
        "display_name": "Hadapsar",
        "station_name": "Hadapsar, Pune - IITM",
        "aliases": [
            "hadapsar",
            "hadapsar pune",
            "hadapsar iitm",
            "hadapsar pune iitm",
            "hadapsar station",
        ],
        "latitude": 18.500774,
        "longitude": 73.937915,
    },

    "Karve Road": {
        "display_name": "Karve Road",
        "station_name": "Karve Road, Pune - MPCB",
        "aliases": [
            "karve road",
            "karve",
            "karve road pune",
            "karve road mpcb",
            "karve road pune mpcb",
            "karve road station",
        ],
        "latitude": 18.488664,
        "longitude": 73.814088,
    },

    "Katraj Dairy": {
        "display_name": "Katraj Dairy",
        "station_name": "Katraj Dairy, Pune - MPCB",
        "aliases": [
            "katraj",
            "katraj dairy",
            "katraj pune",
            "katraj dairy pune",
            "katraj mpcb",
            "katraj dairy mpcb",
            "katraj station",
        ],
        "latitude": 18.501805,
        "longitude": 73.809360,
    },

    "Panchawati Pashan": {
        "display_name": "Panchawati Pashan",
        "station_name": "Panchawati_Pashan, Pune - IITM",
        "aliases": [
            "pashan",
            "panchawati",
            "panchawati pashan",
            "panchawati_pashan",
            "pashan pune",
            "panchawati pashan pune",
            "pashan iitm",
            "panchawati pashan iitm",
        ],
        "latitude": 18.530614,
        "longitude": 73.812351,
    },

    "Revenue Colony Shivajinagar": {
        "display_name": "Revenue Colony-Shivajinagar",
        "station_name": "Revenue Colony-Shivajinagar, Pune - IITM",
        "aliases": [
            "revenue colony",
            "revenue colony shivajinagar",
            "revenue colony-shivajinagar",
            "shivajinagar",
            "shivaji nagar",
            "shivajinagar pune",
            "revenue colony pune",
            "shivajinagar iitm",
        ],
        "latitude": 18.529557,
        "longitude": 73.849141,
    },

    "SPPU": {
        "display_name": "Savitribai Phule Pune University",
        "station_name": "Savitribai Phule Pune University, Pune - MPCB",
        "aliases": [
            "sppu",
            "sppu pune",
            "sppu mpcb",
            "savitribai phule pune university",
            "savitribai phule pune university pune",
            "university",
            "pune university",
            "pune university mpcb",
            "university station",
        ],
        "latitude": 18.552844,
        "longitude": 73.826644,
    },

    "Transport Nagar Nigdi": {
        "display_name": "Transport Nagar-Nigdi",
        "station_name": "Transport Nagar-Nigdi, Pune - IITM",
        "aliases": [
            "transport nagar",
            "transport nagar nigdi",
            "nigdi",
            "nigdi pune",
            "transport nagar pune",
            "transport nagar nigdi iitm",
            "nigdi iitm",
        ],
        "latitude": 18.663927,
        "longitude": 73.767650,
    },
}


def normalize_location_text(value: str | None) -> str:
    """
    Normalize user input for reliable alias matching.
    """
    if not value:
        return ""

    value = unicodedata.normalize("NFKD", str(value))
    value = value.lower().strip()

    value = value.replace("_", " ")
    value = value.replace("-", " ")

    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


_ALIAS_INDEX: dict[str, str] = {}

for canonical, data in PUNE_STATIONS.items():
    _ALIAS_INDEX[normalize_location_text(canonical)] = canonical

    _ALIAS_INDEX[
        normalize_location_text(data["display_name"])
    ] = canonical

    if data.get("station_name"):
        _ALIAS_INDEX[
            normalize_location_text(data["station_name"])
        ] = canonical

    for alias in data.get("aliases", []):
        _ALIAS_INDEX[normalize_location_text(alias)] = canonical


def resolve_pune_location(text: str | None) -> dict[str, Any] | None:
    """
    Resolve a user question/location to a canonical Pune station.

    Returns None when no supported station can be confidently resolved.
    """

    normalized = normalize_location_text(text)

    if not normalized:
        return None

    # Exact match first.
    if normalized in _ALIAS_INDEX:
        canonical = _ALIAS_INDEX[normalized]
        result = dict(PUNE_STATIONS[canonical])
        result["canonical_location"] = canonical
        return result

    # Match longer aliases first.
    matches = []

    for alias, canonical in _ALIAS_INDEX.items():
        if len(alias) < 3:
            continue

        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            matches.append((len(alias), canonical))

    if not matches:
        return None

    # Longest matching alias wins.
    _, canonical = max(matches, key=lambda x: x[0])

    result = dict(PUNE_STATIONS[canonical])
    result["canonical_location"] = canonical

    return result


def get_all_pune_stations() -> list[dict[str, Any]]:
    """
    Return all canonical Pune monitoring stations.
    """
    stations = []

    for canonical, data in PUNE_STATIONS.items():
        item = dict(data)
        item["canonical_location"] = canonical
        stations.append(item)

    return stations


def get_station_by_canonical_name(
    canonical_location: str | None,
) -> dict[str, Any] | None:

    if not canonical_location:
        return None

    return PUNE_STATIONS.get(canonical_location)


def supported_pune_locations() -> list[str]:
    return list(PUNE_STATIONS.keys())
