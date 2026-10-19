"""
Conceptual Knowledge & Definitions Module
==========================================
Provides accurate, concise educational answers for domain terms:
AQI, PM2.5, PM10, NO2, SO2, CO, O3, DBSCAN, SHAP, XGBoost, CPCB, RAG, LangGraph, WeatherAPI.
Prevents conceptual questions from accidentally triggering live API or ML model runs.
"""

from typing import Optional, Dict

CONCEPT_KNOWLEDGE_BASE: Dict[str, Dict[str, str]] = {
    "aqi": {
        "term": "Air Quality Index (AQI)",
        "definition": (
            "The Air Quality Index (AQI) is a standardized metric used by government bodies like CPCB to communicate "
            "how polluted the air currently is or how polluted it is forecast to become. In India, AQI is categorized as:\n"
            "• 0–50: Good\n"
            "• 51–100: Satisfactory\n"
            "• 101–200: Moderate\n"
            "• 201–300: Poor\n"
            "• 301–400: Very Poor\n"
            "• 401–500: Severe\n"
            "It converts complex concentrations of multiple pollutants (PM2.5, PM10, NO2, SO2, CO, O3, NH3, Pb) into a single index value."
        )
    },
    "pm25": {
        "term": "Particulate Matter 2.5 (PM2.5)",
        "definition": (
            "PM2.5 refers to fine inhalable atmospheric particles with aerodynamic diameters of 2.5 micrometers or smaller "
            "(roughly 30 times smaller than a human hair). Key sources include vehicle exhaust, fossil-fuel burning, power generation, "
            "and biomass combustion. Due to their minute size, they penetrate deep into the human respiratory tract and enter the bloodstream, "
            "causing serious cardiovascular and pulmonary disorders. The CPCB 24-hour national standard is 60 µg/m³."
        )
    },
    "pm10": {
        "term": "Particulate Matter 10 (PM10)",
        "definition": (
            "PM10 refers to respirable particulate matter with diameters of 10 micrometers or smaller. "
            "Primary sources include unpaved road dust resuspension, construction and demolition activities, mechanical grinding, and industrial dust. "
            "They irritate the eyes, throat, and upper airways. The CPCB 24-hour national standard is 100 µg/m³."
        )
    },
    "no2": {
        "term": "Nitrogen Dioxide (NO2)",
        "definition": (
            "Nitrogen Dioxide (NO2) is a pungent, reddish-brown gaseous pollutant formed primarily during high-temperature fuel combustion "
            "in motor vehicles, thermal power plants, and industrial boilers. It causes respiratory inflammation and contributes to ground-level ozone "
            "and acid rain. The CPCB 24-hour national standard is 80 µg/m³."
        )
    },
    "so2": {
        "term": "Sulfur Dioxide (SO2)",
        "definition": (
            "Sulfur Dioxide (SO2) is a toxic gas emitted largely from the combustion of sulfur-bearing fossil fuels (such as coal and diesel) "
            "in thermal plants, petroleum refineries, and metallurgical smelters. It aggravates asthma, causes throat constriction, and forms secondary sulfate aerosols. "
            "The CPCB 24-hour national standard is 80 µg/m³."
        )
    },
    "co": {
        "term": "Carbon Monoxide (CO)",
        "definition": (
            "Carbon Monoxide (CO) is a colorless, odorless gas produced by the incomplete combustion of carbon-based fuels (petrol, diesel, wood, coal). "
            "When inhaled, it binds tightly with hemoglobin to form carboxyhemoglobin, significantly reducing oxygen delivery to vital organs. "
            "The CPCB 8-hour national standard is 2.0 mg/m³ (approx 2000 µg/m³)."
        )
    },
    "o3": {
        "term": "Ground-Level Ozone (O3)",
        "definition": (
            "Unlike stratospheric ozone which shields against UV radiation, ground-level ozone is a secondary photochemical pollutant. "
            "It forms when nitrogen oxides (NOx) and volatile organic compounds (VOCs) react in the presence of strong sunlight. "
            "It acts as a powerful lung irritant, triggering asthma attacks and reducing crop yields. The CPCB 8-hour national standard is 100 µg/m³."
        )
    },
    "dbscan": {
        "term": "DBSCAN (Density-Based Spatial Clustering of Applications with Noise)",
        "definition": (
            "DBSCAN is an unsupervised machine learning clustering algorithm. In this system, it groups geographically proximate "
            "monitoring stations with abnormally high pollutant densities into distinct 'pollution hotspot clusters', while labeling isolated "
            "outliers as spatial noise. Unlike K-Means, DBSCAN does not require specifying the number of clusters in advance and can discover "
            "arbitrarily shaped pollution plumes across urban and industrial corridors."
        )
    },
    "shap": {
        "term": "SHAP (SHapley Additive exPlanations)",
        "definition": (
            "SHAP is a game-theoretic model explainability technique based on Shapley values. In this platform, TreeExplainer calculates "
            "the exact marginal contribution of each feature (pollutant lags, meteorological variables, temporal factors) to the XGBoost "
            "PM2.5 prediction. It guarantees additive consistency: the model prediction equals the baseline expected value plus the sum of all "
            "individual feature attributions. It provides transparency into why a prediction increased or decreased."
        )
    },
    "xgboost": {
        "term": "XGBoost (Extreme Gradient Boosting)",
        "definition": (
            "XGBoost is a gradient-boosted decision tree library engineered for speed and tabular accuracy. In our system, "
            "a Multi-Station XGBoost Regressor trained on 171,000+ hourly CPCB observations uses temporal lags, rolling averages, "
            "meteorological conditions, and station embeddings to generate next-hour PM2.5 forecasts."
        )
    },
    "forecasting": {
        "term": "Air Pollution Forecasting",
        "definition": (
            "Pollution forecasting is the application of statistical, atmospheric, and machine learning models "
            "to project ambient concentrations of critical pollutants (such as PM2.5 and PM10) several hours or days into the future. "
            "In this system, a gradient-boosted XGBoost regressor leverages sequential lag concentrations (t-1 to t-24), "
            "rolling statistical features, boundary-layer meteorological data (wind, temperature, humidity), and geographic coordinates "
            "to predict next-hour PM2.5 levels with quantitative confidence bounds."
        )
    },
    "cpcb": {
        "term": "Central Pollution Control Board (CPCB)",
        "definition": (
            "CPCB is India's statutory organization constituted under the Water (Prevention and Control of Pollution) Act, 1974, "
            "and entrusted with powers under the Air (Prevention and Control of Pollution) Act, 1981. It operates the Continuous Ambient Air "
            "Quality Monitoring Stations (CAAQMS) network across India and establishes National Ambient Air Quality Standards (NAAQS)."
        )
    },
    "rag": {
        "term": "Retrieval-Augmented Generation (RAG)",
        "definition": (
            "RAG is an AI architecture that enhances language models by retrieving relevant factual documents from a curated knowledge base "
            "before generating an answer. In this project, RAG retrieves verified CPCB regulatory guidelines, NAAQS standards, and the Air Act "
            "to answer policy and legal questions accurately without hallucinations."
        )
    },
    "langgraph": {
        "term": "LangGraph",
        "definition": (
            "LangGraph is a framework for building stateful, multi-agent AI workflows as directed graphs. In this system, "
            "it orchestrates user intent routing, live environmental retrieval, XGBoost forecasting, DBSCAN hotspot clustering, "
            "and policy RAG generation through coordinated stateful nodes."
        )
    },
    "weatherapi": {
        "term": "WeatherAPI",
        "definition": (
            "WeatherAPI is an external meteorological provider integrated into this platform to fetch live ambient weather conditions "
            "(temperature, humidity, pressure, wind velocity, precipitation) and real-time indicative air-quality readings for any "
            "geographical location in India."
        )
    },
    "naaqs": {
        "term": "National Ambient Air Quality Standards (NAAQS)",
        "definition": (
            "National Ambient Air Quality Standards (NAAQS) are statutory standards notified by the Central Pollution "
            "Control Board (CPCB) under the Air (Prevention and Control of Pollution) Act, 1981. They designate allowable "
            "threshold concentrations for 12 critical air pollutants across India, including PM2.5 (60 ug/m3 24-hr, 40 ug/m3 annual), "
            "PM10 (100 ug/m3 24-hr, 60 ug/m3 annual), NO2 (80 ug/m3 24-hr), and SO2 (80 ug/m3 24-hr) to safeguard public health and the environment."
        )
    },
}


def get_conceptual_explanation(question: str) -> Optional[str]:
    """
    Check if the user is asking a definitional / conceptual question
    and return an authoritative answer without executing live API or model pipelines.
    """
    if not question:
        return None

    import re
    q = question.lower().strip()
    words = re.sub(r"[?!.,;:]+", "", q).split()

    # Definitional query patterns
    def_prefixes = [
        "what is", "what are", "define", "definition of", "meaning of", "explain",
        "describe", "overview of", "tell me about", "what does", "concept of",
        "full form of", "stand for", "how does", "what meant by"
    ]
    is_def_pattern = any(p in q for p in def_prefixes)

    # Conceptual keywords mapping
    term_map = {
        "aqi": ["aqi", "air quality index"],
        "pm25": ["pm2.5", "pm25", "pm 2.5", "fine particulate"],
        "pm10": ["pm10", "pm 10", "respirable particulate"],
        "no2": ["no2", "nitrogen dioxide"],
        "so2": ["so2", "sulfur dioxide"],
        "co": ["carbon monoxide"],
        "o3": ["ozone", "o3", "ground-level ozone"],
        "dbscan": ["dbscan"],
        "shap": ["shap", "shapley"],
        "xgboost": ["xgboost", "xgb"],
        "cpcb": ["cpcb", "central pollution control board"],
        "rag": ["rag", "retrieval augmented generation"],
        "langgraph": ["langgraph"],
        "weatherapi": ["weatherapi", "weather api"],
        "forecasting": ["pollution forecasting", "air pollution forecasting", "forecasting"],
        "naaqs": ["naaqs", "naqqs", "naqs", "national ambient air quality standards"],
    }

    # If asking what NAAQS/regulation says about a specific pollutant or rules, route to RAG
    if any(p in q for p in ["ncap", "air act", "regulation", "say about", "rules on"]) or (
        ("naaqs" in q or "naqqs" in q) and any(pol in q for pol in ["pm2.5", "pm25", "pm10", "no2", "so2", "co", "o3", "standard for", "say about", "limit"])
    ):
        return None

    # Check if asking to execute analysis on an actual location, prediction, or data
    has_exec_or_loc = any(
        loc_term in q for loc_term in [
            " in ", " of ", " for ", " at ", "run ", "using ", "prediction", "forecast",
            "hotspot", "hotspots", "cluster", "clusters", "pune", "mumbai", "delhi", "wagholi",
            "alandi", "nagpur", "station", "current", "today", "live", "values", "importance"
        ]
    )

    if has_exec_or_loc:
        # Allow only pure definitional queries like "what is DBSCAN?", "define SHAP", "explain PM2.5"
        has_pure_def = any(
            re.search(r"^(?:what\s+is|what\s+are|define|explain|meaning\s+of|describe)\s+(?:the\s+)?(?:term\s+)?" + re.escape(alias) + r"[?!.]?$", q)
            for aliases in term_map.values() for alias in aliases
        )
        if not has_pure_def:
            return None

    # Check matches across term_map
    for key, aliases in term_map.items():
        for alias in aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", q):
                item = CONCEPT_KNOWLEDGE_BASE[key]
                term = item['term']
                return f"{term}\n" + ("=" * len(term)) + f"\n\n{item['definition']}"

    return None
