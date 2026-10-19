def classify_intent(question: str) -> str:
    """
    Determine which pollution agent should handle the
    user's question.

    Returns one of:
        live_aqi
        forecast
        anomaly
        hotspot
        policy
    """

    if not question:
        return "unknown"

    q = question.lower().strip()

    # ========================================================
    # LIVE AQI
    # ========================================================

    live_keywords = [
        "live aqi",
        "current aqi",
        "aqi now",
        "current air quality",
        "live air quality",
        "air quality now",
        "current pollution",
        "live pollution",
        "pollution now",
        "current pm2.5",
        "live pm2.5",
    ]

    if any(word in q for word in live_keywords):
        return "live_aqi"

    # ========================================================
    # FORECAST
    # ========================================================

    forecast_keywords = [
        "forecast",
        "predict",
        "prediction",
        "next hour",
        "next 1 hour",
        "future pm2.5",
        "tomorrow pm2.5",
        "predict pm2.5",
        "forecast pm2.5",
    ]

    if any(word in q for word in forecast_keywords):
        return "forecast"

    # ========================================================
    # ANOMALY
    # ========================================================

    anomaly_keywords = [
        "anomaly",
        "anomalous",
        "unusual pollution",
        "abnormal pollution",
        "pollution spike",
        "pollution abnormal",
    ]

    if any(word in q for word in anomaly_keywords):
        return "anomaly"

    # ========================================================
    # HOTSPOT
    # ========================================================

    hotspot_keywords = [
        "hotspot",
        "hotspots",
        "pollution hotspot",
        "pollution hotspots",
        "polluted area",
        "most polluted area",
        "cluster",
        "clusters",
    ]

    if any(word in q for word in hotspot_keywords):
        return "hotspot"

    # ========================================================
    # POLICY / KNOWLEDGE
    # ========================================================

    policy_keywords = [
        "policy",
        "policies",
        "guideline",
        "guidelines",
        "ncaps",
        "ncap",
        "cpcb",
        "reduce pollution",
        "control pollution",
        "pollution control",
        "measures to reduce",
        "what measures",
        "what can be done",
        "government",
        "standard",
        "standards",
    ]

    if any(word in q for word in policy_keywords):
        return "policy"

    # Default
    return "policy"