"""
Advanced Location Extraction & Multi-City Parsing Service
==========================================================
Accurately extracts:
1. Single location (City, district, town, locality) without picking up question phrases.
2. Multiple locations for comparison queries ("Compare Pune and Mumbai", "Delhi vs Nagpur").
3. Distinguishes conceptual queries from geographical queries.
4. Prevents common stop-words, generic verbs, and numbers from being misidentified as cities.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from backend.services.universal_location_resolver import LOCAL_COORDINATE_REGISTRY
from backend.services.pune_locations import PUNE_STATIONS

# Stopwords and generic terms that must NEVER be returned as a location
INVALID_LOCATION_WORDS = {
    "what", "is", "the", "a", "an", "are", "of", "in", "for", "at", "to", "and", "or", "vs", "versus",
    "between", "current", "today", "now", "live", "pollution", "air", "quality", "aqi",
    "pm25", "pm2.5", "pm10", "no2", "so2", "co", "o3", "weather", "forecast", "prediction",
    "predict", "hotspot", "hotspots", "cluster", "clusters", "dbscan", "shap", "xgboost",
    "cpcb", "mpcb", "naaqs", "rag", "report", "city", "place", "area", "zone", "here", "there",
    "hello", "hi", "hey", "help", "thanks", "thank", "bye", "good", "bad", "moderate", "poor",
    "explain", "meaning", "definition", "compare", "comparison", "difference", "higher", "lower",
    "better", "worse", "which", "how", "why", "who", "where", "when", "show", "give", "tell",
    "france", "paris", "joke", "stock", "stocks", "price", "prices", "capital",
    "oven", "bread", "cake", "food", "car", "game", "match", "movie", "book", "song", "code"
}

# Canonical mapping for common Indian city typos, historical names, and transliterations
LOCATION_ALIASES: dict[str, str] = {
    "chenai": "Chennai",
    "channai": "Chennai",
    "madras": "Chennai",
    "bombay": "Mumbai",
    "mumbay": "Mumbai",
    "bangalore": "Bengaluru",
    "banglore": "Bengaluru",
    "bengalore": "Bengaluru",
    "calcutta": "Kolkata",
    "wagoli": "Wagholi",
    "alandee": "Alandi",
    "karadi": "Kharadi",
    "hadpsar": "Hadapsar",
    "shivaji nagar": "Shivajinagar",
    "baroda": "Vadodara",
    "trivandrum": "Thiruvananthapuram",
    "cochin": "Kochi",
    "gurgaon": "Gurugram",
    "poona": "Pune",
    "puna": "Pune",
    "sambhajinagar": "Chhatrapati Sambhajinagar",
}

# Known major Indian cities & states for regex lookup
KNOWN_INDIAN_PLACES = [
    # Metros & Capitals
    "pune", "mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "banglore", "bengalore", "hyderabad",
    "chennai", "chenai", "channai", "madras", "kolkata", "calcutta", "ahmedabad", "chandigarh", "jaipur", "lucknow", "bhopal",
    "patna", "ranchi", "shimla", "dehradun", "srinagar", "thiruvananthapuram", "trivandrum",
    
    # Maharashtra Cities & Districts
    "nagpur", "nashik", "aurangabad", "chhatrapati sambhajinagar", "sambhajinagar", "solapur",
    "kolhapur", "thane", "navi mumbai", "kalyan", "dombivli", "vasai", "virar",
    "beed", "satara", "sangli", "amravati", "nanded", "jalgaon", "akola", "latur",
    "dhule", "ahmednagar", "chandrapur", "parbhani", "jalna", "ratnagiri",
    
    # Pune Localities & Suburbs
    "alandi", "alandee", "wagholi", "wagoli", "hadapsar", "hadpsar", "karve road", "karve nagar", "shivajinagar", "shivaji nagar",
    "kothrud", "baner", "hinjewadi", "hinjawadi", "wakad", "bhosari", "bhumkar nagar",
    "pashan", "nigdi", "katraj", "dhankawadi", "viman nagar", "kharadi", "karadi", "magarpatta",
    "kalyani nagar", "chakan", "akurdi", "pimpri", "chinchwad", "pimpri chinchwad",
    "sppu", "aundh", "bavdhan", "swargate", "camp", "yerawada", "dhanori", "lohegaon",
    "kondhwa", "warje", "ravet", "moshi", "talegaon", "fc road", "poona", "puna",
    
    # Other Major Indian Cities
    "gurugram", "gurgaon", "noida", "ghaziabad", "faridabad", "kanpur", "varanasi",
    "agra", "meerut", "indore", "gwalior", "jabalpur", "surat", "vadodara", "baroda", "rajkot",
    "visakhapatnam", "vijayawada", "coimbatore", "madurai", "kochi", "cochin", "kozhikode",
    "mysuru", "mangalore", "hubballi", "guwahati", "bhubaneswar", "cuttack", "amritsar",
    "ludhiana", "jalandhar", "raipur", "durgapur", "asansol", "siliguri"
]

# Sort by length descending so multi-word locations like "Navi Mumbai" match before "Mumbai"
SORTED_PLACES = sorted(list(set(KNOWN_INDIAN_PLACES)), key=len, reverse=True)


def is_valid_location_candidate(text: str) -> bool:
    """Validate that an extracted phrase is genuinely a location and not a question fragment."""
    if not text or len(text.strip()) < 2:
        return False
    words = re.sub(r"[?!.,;:]+", "", text.lower()).split()
    if not words:
        return False
    # If all words are in stop words or invalid words, reject
    if all(w in INVALID_LOCATION_WORDS for w in words):
        return False
    # If it is numeric
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text.strip()):
        return False
    return True


def extract_locations_from_text(text: str) -> List[str]:
    """
    Extract all distinct valid locations mentioned in the query.
    Handles single locations as well as multi-city lists / comparisons.
    """
    if not text:
        return []

    # If it is a conceptual definition question, do not extract any location
    from backend.services.conceptual_knowledge import get_conceptual_explanation
    if get_conceptual_explanation(text) is not None:
        return []

    # If text is only greeting/farewell/help
    raw_lower = text.strip().lower()
    if raw_lower in {"hello", "hi", "hey", "namaste", "bye", "goodbye", "thanks", "help"}:
        return []

    norm = text.lower()

    # Check for composite 'Locality, City' pattern (e.g., 'Wagholi, Pune', 'Bhosari, Pune')
    # only when it's not a comparison query (i.e. no 'and', 'vs', 'compare')
    is_comparison = any(term in norm for term in ["compare", "vs", "versus", " and ", "between", "higher"])
    if not is_comparison:
        comp_match = re.search(
            r"\b([A-Za-z\s]{3,25}),\s*(pune|mumbai|delhi|nagpur|bengaluru|nashik|maharashtra)\b",
            text,
            flags=re.IGNORECASE
        )
        if comp_match:
            loc_raw = comp_match.group(1).strip()
            # Strip common leading question prefixes like "report for", "quality in", "for"
            loc_part = re.sub(
                r"^(?:(?:give\s+me\s+)?(?:the\s+)?(?:latest\s+)?(?:air\s+quality\s+)?(?:pollution\s+)?(?:report\s+)?(?:for|in|of|at)\s+)+",
                "",
                loc_raw,
                flags=re.IGNORECASE
            ).strip()
            city_part = comp_match.group(2).strip().title()
            if is_valid_location_candidate(loc_part):
                return [f"{loc_part.title()}, {city_part}"]

    found_locations: List[str] = []
    matched_spans = []

    # 1. Search known Indian places (multi-word first)
    for place in SORTED_PLACES:
        pattern = r"\b" + re.escape(place) + r"\b"
        for match in re.finditer(pattern, norm):
            span = match.span()
            # Check overlap with already found longer span
            if not any(s[0] <= span[0] and s[1] >= span[1] for s in matched_spans):
                # Format properly (resolve aliases, preserve Pune localities / proper capitalization)
                canonical_mapped = LOCATION_ALIASES.get(place.lower())
                if canonical_mapped:
                    formatted = canonical_mapped
                elif place == "sppu":
                    formatted = "SPPU"
                elif place == "fc road":
                    formatted = "FC Road"
                elif place == "delhi" and "new delhi" not in found_locations:
                    formatted = "Delhi"
                else:
                    formatted = place.title()
                
                if formatted not in found_locations:
                    found_locations.append(formatted)
                    matched_spans.append(span)

    # 2. Check for explicit preposition patterns if no known place was matched:
    # Require environmental context anchor in the query to avoid matching non-environmental queries
    if not found_locations:
        has_env_context = any(
            t in norm for t in [
                "aqi", "air quality", "pollution", "pollutant", "pm25", "pm2.5", "pm10",
                "weather", "forecast", "predict", "hotspot", "smog", "temperature", "humidity", "rain"
            ]
        )
        if has_env_context:
            prep_patterns = [
                r"\b(?:air quality|aqi|weather|pollution|forecast)\s+(?:in|of|for|at)\s+([A-Za-z\s]{2,30})",
                r"\b(?:in|at|of|for)\s+([A-Za-z\s]{2,30})(?:\?|\.|$|,|\s+today|\s+now|\s+currently)",
            ]
            for pat in prep_patterns:
                m = re.search(pat, text, flags=re.IGNORECASE)
                if m:
                    cand = m.group(1).strip()
                    cand_clean = re.sub(r"\b(today|now|right now|currently|please|tell me)\b.*$", "", cand, flags=re.IGNORECASE).strip()
                    if is_valid_location_candidate(cand_clean):
                        found_locations.append(cand_clean.title())
                        break

    return found_locations


def extract_single_location(text: str, fallback_memory: Optional[str] = None) -> Optional[str]:
    """
    Extract a single primary location from text.
    If none found, optionally falls back to conversational session memory.
    """
    locs = extract_locations_from_text(text)
    if locs:
        return locs[0]
    return fallback_memory


def extract_comparison_locations(text: str, memory_locations: Optional[List[str]] = None) -> List[str]:
    """
    Extract multiple cities for comparison queries (e.g. 'Compare Pune and Mumbai').
    Resolves anaphora like 'Compare both' or 'compare them' using session memory.
    """
    locs = extract_locations_from_text(text)
    if len(locs) >= 2:
        return locs

    norm = text.lower()
    # Handle anaphora: "compare both", "compare the two", "which is higher"
    if any(p in norm for p in ["compare both", "compare them", "compare the two", "which has higher", "which is more polluted"]):
        if memory_locations and len(memory_locations) >= 2:
            return memory_locations[:2]

    # If only 1 city was in current query, but user said "what about Mumbai?" after discussing Pune
    if len(locs) == 1 and memory_locations:
        prior = [m for m in memory_locations if m.lower() != locs[0].lower()]
        if prior:
            return [prior[-1], locs[0]]

    return locs
