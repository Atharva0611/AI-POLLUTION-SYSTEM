from typing import TypedDict, Any, List


class PollutionState(TypedDict, total=False):

    # ========================================================
    # INPUT
    # ========================================================

    question: str
    previous_question: str
    is_followup: bool
    input_data: Any

    # ========================================================
    # ROUTING & ORCHESTRATION
    # ========================================================

    intent: str
    location: str
    session_id: str
    direct_message: str
    comparison_locations: List[str]
    requested_intents: List[str]
    forecast_data: Any
    dbscan_data: Any

    # ========================================================
    # WEATHERAPI  (live AQI / weather / forecast)
    # ========================================================

    environment: Any       # full dict from get_environment_for_user()

    # ========================================================
    # RAG  (policy / regulation / guideline)
    # ========================================================

    policy: Any            # string answer from answer_question()

    # ========================================================
    # CPCB  (station / historical data)
    # ========================================================

    cpcb_data: Any         # list of DB rows or WeatherAPI snapshot
    cpcb_source: str

    # ========================================================
    # DBSCAN  (hotspot / anomaly / clustering)
    # ========================================================

    dbscan_clusters: Any   # list of cluster dicts
    dbscan_fallback: Any   # fallback snapshot dict
    dbscan_source: str

    # ========================================================
    # RECOMMENDATION  (action / mitigation advice)
    # ========================================================

    recommendations: Any   # list of recommendation strings

    # ========================================================
    # LEGACY  (kept for backward compat)
    # ========================================================

    latitude: float
    longitude: float
    live_aqi: Any
    live_aqi_location: str
    live_aqi_success: bool
    forecast_pm25: float
    forecast_success: bool
    anomaly_detected: bool
    anomaly_score: float
    anomaly_success: bool
    hotspot_clusters: Any
    hotspot_success: bool
    retrieved_documents: Any
    policy_answer: str
    policy_success: bool

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    final_answer: str
    error: str