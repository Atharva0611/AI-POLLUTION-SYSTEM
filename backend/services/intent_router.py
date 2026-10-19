"""
Intent Router & Multi-Intent Classifier
=======================================
Deterministic rule-based intent classifier supporting 16 distinct intents:
 1. greeting
 2. conversation (farewell, gratitude, help)
 3. conceptual_definition (what is AQI, PM2.5, DBSCAN, SHAP, etc.)
 4. comparison (compare cities)
 5. live_aqi (current air quality readings)
 6. forecast (future PM2.5 / trend prediction)
 7. dbscan (hotspot clustering execution)
 8. shap (model feature attribution analysis)
 9. cpcb (station data, historical observations)
10. policy_rag (NAAQS, Air Act, regulations)
11. recommendation (pollution mitigation actions)
12. weather (meteorological parameters: temp, rain, wind)
13. historical_data
14. source_analysis
15. unsupported (out of domain)
16. clarification_required
"""

import re
from typing import Dict, Any, Optional

from backend.services.input_validator import validate_user_input
from backend.services.location_extractor import (
    extract_single_location,
    extract_comparison_locations,
)
from backend.services.conceptual_knowledge import get_conceptual_explanation

# Keyword patterns per intent
COMPARISON_TERMS = [
    r"\bcompare\b", r"\bcomparison\b", r"\bvs\b", r"\bversus\b",
    r"\bhigher\s+(?:aqi|pollution|pm25|pm2\.5)\b",
    r"\bwhich\s+(?:city|place)\s+(?:has|is)\s+(?:more|higher|better|worse)\b",
    r"\bwhich\s+is\s+(?:more\s+polluted|cleaner)\b",
]

DBSCAN_EXEC_TERMS = [
    r"\b(?:pollution\s+)?hotspots?\b",
    r"\bcluster(?:s|ing)?\b",
    r"\bspatial\s+clustering\b",
    r"\banomaly\s+detection\b",
    r"\bidentify\s+hotspots?\b",
    r"\bdetect\s+hotspots?\b",
    r"\bmost\s+polluted\s+(?:zone|area|locality)\b",
    r"\bworst\s+(?:zone|area)\b",
]

FORECAST_TERMS = [
    r"\bforecast\b", r"\bpredict(?:ion)?\b", r"\bnext\s+hour\b",
    r"\btomorrow\b", r"\bfuture\s+(?:aqi|pollution|pm25|pm2\.5)\b",
    r"\bprojected\b",
]

SHAP_EXEC_TERMS = [
    r"\bshap\b", r"\bshapley\b", r"\bfeature\s+importance\b",
    r"\bfeature\s+attribution\b", r"\bexplain\s+(?:the\s+)?(?:model|prediction|forecast)\b",
    r"\bwhy\s+is\s+the\s+prediction\b",
]

POLICY_RAG_TERMS = [
    r"\bnaaqs\b", r"\bncap\b", r"\bregulation(?:s)?\b", r"\bguideline(?:s)?\b",
    r"\bpolicy\b", r"\bpolicies\b", r"\bcompliance\b", r"\blegal\s+limit\b",
    r"\bair\s+act\b", r"\benvironment\s+act\b", r"\bemission\s+standards?\b",
    r"\bconstruction\s+dust\b", r"\broad\s+dust\b", r"\bopen\s+burning\b",
    r"\bwaste\s+burning\b", r"\bwhat\s+does\s+cpcb\s+say\b",
]

RECOMMENDATION_TERMS = [
    r"\brecommendation(?:s)?\b", r"\bmitigation\b", r"\bwhat\s+action\b",
    r"\bwhat\s+steps?\b", r"\bwhat\s+can\s+be\s+done\b", r"\bhow\s+to\s+reduce\b",
    r"\bhow\s+to\s+improve\b", r"\bsuggest(?:ions?)?\b", r"\badvice\b",
    r"\bpreventive\s+measures?\b",
]

SOURCE_ANALYSIS_TERMS = [
    r"\bsource(?:s)?\s+of\b", r"\bpollution\s+source(?:s)?\b",
    r"\bwhat\s+causes\b", r"\bcause(?:s)?\s+of\b",
    r"\bvehicular\s+emission(?:s)?\b", r"\bindustrial\s+emission(?:s)?\b",
    r"\bstubble\s+burning\b", r"\bwhere\s+does\s+(?:the\s+)?pollution\s+come\b",
]

HISTORICAL_TERMS = [
    r"\bhistorical\b", r"\bpast\s+(?:data|aqi|pollution|trend|readings?)\b",
    r"\blast\s+(?:week|month|year|day)\b", r"\byesterday\b",
]

CPCB_STATION_TERMS = [
    r"\bcpcb\s+station\b", r"\bmpcb\s+station\b", r"\bmonitoring\s+station\b",
    r"\bstation\s+data\b", r"\bstation\s+reading\b", r"\bofficial\s+reading\b",
    r"\bcaaqms\b",
]

WEATHER_TERMS = [
    r"\bweather\b", r"\btemperature\b", r"\bhumidity\b", r"\brainfall\b",
    r"\braining\b", r"\bwind\s+speed\b", r"\bwind\s+direction\b",
]

LIVE_AQI_TERMS = [
    r"\baqi\b", r"\bair\s+quality\b", r"\bpm2\.5\b", r"\bpm25\b", r"\bpm10\b",
    r"\bno2\b", r"\bso2\b", r"\bco\b", r"\bo3\b", r"\bpollution\b",
    r"\blive\b", r"\bcurrent\b",
]

ALL_POLLUTION_DOMAIN_TERMS = (
    COMPARISON_TERMS + DBSCAN_EXEC_TERMS + FORECAST_TERMS + SHAP_EXEC_TERMS +
    POLICY_RAG_TERMS + RECOMMENDATION_TERMS + SOURCE_ANALYSIS_TERMS +
    HISTORICAL_TERMS + CPCB_STATION_TERMS + WEATHER_TERMS + LIVE_AQI_TERMS
)


def classify_intent(question: str, memory_locations: Optional[list] = None) -> str:
    """
    Deterministic rule-based intent classification supporting the 16 core intents:
    1. greeting
    2. conversation
    3. live_aqi
    4. pollutant_information
    5. weather
    6. forecast
    7. historical_data
    8. cpcb
    9. dbscan
    10. shap
    11. source_analysis
    12. policy_rag
    13. recommendation
    14. comparison
    15. unsupported
    16. clarification_required
    """
    val = validate_user_input(question)
    if not val["valid"]:
        if val["type"] == "greeting":
            return "greeting"
        elif val["type"] in {"farewell", "gratitude", "help"}:
            return "conversation"
        elif val["type"] in {"empty", "numeric"}:
            return "clarification_required"
        elif val["type"] == "unsupported":
            return "unsupported"
        return "clarification_required"

    q = question.lower().strip()

    # 1. Conceptual definition queries (e.g. "What is DBSCAN?", "Explain PM2.5", "Define AQI")
    conceptual_ans = get_conceptual_explanation(question)
    if conceptual_ans is not None:
        if any(term in q for term in ["pm2.5", "pm25", "pm10", "no2", "so2", "co", "o3", "aqi", "ozone"]):
            return "pollutant_information"
        elif "dbscan" in q:
            return "pollutant_information"
        elif "shap" in q:
            return "pollutant_information"
        return "pollutant_information"

    # 2. Policy comparisons must be routed to RAG first.
    policy_comparison_terms = (
        r"\bncap\b",
        r"\bgrap\b",
        r"\bnational\s+clean\s+air\s+programme\b",
        r"\bnational\s+clean\s+air\s+program\b",
        r"\bgraded\s+response\s+action\s+plan\b",
    )

    if any(re.search(pat, q) for pat in policy_comparison_terms):
        return "policy_rag"

    # 3. Ordinary city comparisons.
    for pat in COMPARISON_TERMS:
        if re.search(pat, q):
            comp_locs = extract_comparison_locations(
                question,
                memory_locations=memory_locations
            )
            if len(comp_locs) >= 2 or "compare" in q or "both" in q:
                return "comparison"

    # 3. SHAP queries (explain model prediction, feature attribution)
    for pat in SHAP_EXEC_TERMS:
        if re.search(pat, q):
            return "shap"

    # 4. Forecast queries
    for pat in FORECAST_TERMS:
        if re.search(pat, q):
            return "forecast"

    # 5. DBSCAN Hotspots execution queries
    for pat in DBSCAN_EXEC_TERMS:
        if re.search(pat, q):
            return "dbscan"

    # 6. Source Analysis queries
    for pat in SOURCE_ANALYSIS_TERMS:
        if re.search(pat, q):
            return "source_analysis"

    # 7. Historical Data queries
    for pat in HISTORICAL_TERMS:
        if re.search(pat, q):
            return "historical_data"

    # 8. CPCB station queries
    for pat in CPCB_STATION_TERMS:
        if re.search(pat, q):
            return "cpcb"

    # 9. Policy RAG queries
    for pat in POLICY_RAG_TERMS:
        if re.search(pat, q):
            return "policy_rag"

    # 10. Recommendation queries
    for pat in RECOMMENDATION_TERMS:
        if re.search(pat, q):
            return "recommendation"

    # 11. Weather queries
    for pat in WEATHER_TERMS:
        if re.search(pat, q):
            return "weather"

    # 12. Live AQI queries
    for pat in LIVE_AQI_TERMS:
        if re.search(pat, q):
            return "live_aqi"

    # 13. If query explicitly mentions a valid geographical location
    loc = extract_single_location(question)
    if loc:
        return "live_aqi"

    # 14. If none of the domain keywords or locations are found, it is UNSUPPORTED
    # Do NOT classify unknown inputs as live AQI or weather or policy RAG
    has_domain_keyword = any(re.search(pat, q) for pat in ALL_POLLUTION_DOMAIN_TERMS)
    if not has_domain_keyword:
        return "unsupported"

    # Fallback to policy_rag if general pollution question
    return "policy_rag"


def get_intent_and_location(question: str, memory_location: Optional[str] = None) -> Dict[str, Any]:
    """Return intent and only assign a default location when appropriate."""
    intent = classify_intent(question)
    single_loc = extract_single_location(
        question,
        fallback_memory=memory_location
    )
    comp_locs = extract_comparison_locations(
        question,
        memory_locations=[memory_location] if memory_location else None
    )

    # Definitions and unrelated questions do not need a city.
    if intent in {
        "pollutant_information",
        "unsupported",
        "clarification_required",
        "greeting",
        "conversation",
    }:
        location = single_loc
    else:
        # Preserve Pune as the default for environmental operations.
        location = single_loc or "Pune"

    return {
        "intent": intent,
        "location": location,
        "comparison_locations": comp_locs,
    }


def extract_location(question: str) -> Optional[str]:
    """Compatibility function matching old intent_router.py signature."""
    return extract_single_location(question)
