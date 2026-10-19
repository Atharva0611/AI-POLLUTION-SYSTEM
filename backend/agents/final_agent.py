from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TypedDict

import pandas as pd
from langgraph.graph import START, END, StateGraph

from backend.agents.policy_agent import answer_question
from backend.services.india_environment import get_environment_for_user, _extract_location_from_question


class FinalState(TypedDict, total=False):
    question: str
    route: str
    requested_routes: list
    environment: dict
    rag: Any
    dbscan: dict
    forecast_shap: dict
    final_answer: str


# ORIVA_ROUTER_V2
import re

POLICY_TERMS = {
    "cpcb", "naaqs", "national ambient air quality", "standard", "standards",
    "regulation", "regulations", "policy", "policies", "guideline", "guidelines",
    "compliance", "legal limit", "emission standard", "emission standards",
    "road dust", "construction dust", "open burning", "air act",
}

DBSCAN_TERMS = {
    "hotspot", "hotspots", "cluster", "clusters", "clustering", "dbscan",
    "spatial analysis", "polluted zone", "polluted area", "most polluted area",
    "worst area", "worst zone", "high pollution zone",
}

FORECAST_TERMS = {
    "forecast", "forecasting", "predict", "prediction", "predicting",
    "future pm2.5", "tomorrow pm2.5", "next hour", "next 1 hour",
    "next 24 hours", "next 24 hour", "future air quality",
}

SHAP_TERMS = {
    "shap", "feature importance", "explainability", "model explanation",
    "why did the model", "why did prediction", "prediction explanation",
}

WEATHER_TERMS = {
    "weather", "temperature", "rain", "rainfall", "wind speed",
    "wind direction", "humidity", "will it rain",
}

LIVE_AQI_TERMS = {
    "aqi", "air quality index", "current pollution", "current air quality",
    "live pollution", "live aqi", "pollution level", "pm2.5", "pm 2.5",
    "pm10", "pm 10", "nitrogen dioxide", "no2", "sulfur dioxide", "so2",
    "ozone", "carbon monoxide",
}

CONVERSATION_EXACT = {
    "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "help", "what can you do", "who are you",
    "how are you", "exit", "quit", "q", "bye", "goodbye",
}

CONCEPTUAL_STARTS = (
    "what is ", "what are ", "define ", "meaning of ", "explain ",
    "tell me about ", "describe ", "how does ", "how do ",
    "why does ", "why do ", "difference between ",
)


def _has_term(text: str, terms: set[str]) -> bool:
    text = re.sub(r"[^a-z0-9.#]+", " ", text.lower()).strip()
    padded = f" {text} "
    for term in terms:
        normalized = re.sub(r"[^a-z0-9.#]+", " ", term.lower()).strip()
        if f" {normalized} " in padded:
            return True
    return False


def _is_conceptual_question(question: str) -> bool:
    """Recognize learning requests, but not requests for current/live data."""
    import re

    low = re.sub(r"\s+", " ", question.lower().strip())

    # Current/live requests take precedence over conceptual wording.
    action_phrases = (
        "current", "currently", "right now", "live", "today",
        "tomorrow", "this week", "next 24 hours", "latest",
        "check ", "fetch ", "get ", "show me the current",
        "what is the current", "what's the current",
        "compare ", "find hotspots", "identify hotspots",
        "predict ", "forecast ",
    )
    if any(phrase in low for phrase in action_phrases):
        return False

    conceptual_prefixes = (
        "what is ", "what are ", "who is ", "define ",
        "definition of ", "meaning of ", "explain ",
        "can you explain ", "could you explain ",
        "please explain ", "tell me about ",
        "can you tell me about ", "describe ",
        "how does ", "how do ", "why does ", "why do ",
        "what does ", "what do ", "difference between ",
        "give me a beginner explanation of ",
        "give me a simple explanation of ",
        "help me understand ", "teach me about ",
        "i want to understand ", "i would like to understand ",
        "i want to learn about ", "i would like to learn about ",
    )

    if low.startswith(conceptual_prefixes):
        return True

    learning_phrases = (
        "in simple words", "in simple terms", "for beginners",
        "beginner explanation", "full form of ", "stands for",
        "what is meant by ", "how it works",
    )
    return any(phrase in low for phrase in learning_phrases)


def intent_node(state):
    """Route by the user's primary intent, not incidental time/location words."""
    question = str(state.get("question", "") or "").strip()
    low = re.sub(r"\s+", " ", question.lower()).strip()
    normalized = re.sub(r"[^a-z0-9.#]+", " ", low).strip()

    # Phase 4: detect explicit multi-capability requests before single-route
    # priority rules (e.g. "AQI, forecast, hotspots, and CPCB standards").
    action_request = any(term in normalized for term in (
        "show", "give", "find", "identify", "forecast", "predict",
        "explain", "compare", "analyze", "analyse", "report",
    ))
    if action_request:
        requested_routes = []
        has_live = any(term in normalized for term in (
            "current aqi", "live aqi", "current air quality",
            "current pollution", "right now",
        ))
        has_forecast = any(term in normalized for term in (
            "forecast", "predict", "prediction", "tomorrow",
            "next hour", "next 24 hours",
        ))
        has_hotspots = any(term in normalized for term in (
            "hotspot", "hot spots", "dbscan", "pollution clusters",
        ))
        has_policy = any(term in normalized for term in (
            "cpcb", "naaqs", "national ambient air quality",
            "pm2.5 standard", "pm 2.5 standard",
            "air quality standard", "pollution regulation",
        ))

        if has_live:
            requested_routes.append("weather")
        if has_forecast:
            requested_routes.append("forecast_shap")
        if has_hotspots:
            requested_routes.append("dbscan")
        if has_policy:
            requested_routes.append("rag")

        if len(requested_routes) >= 2:
            return {
                "route": "multi_agent",
                "requested_routes": requested_routes,
                "question": question,
            }

    if not low:
        return {"route": "conversation"}

    # Keep the benchmark's farewell label consistent with conversation.
    if low in {"goodbye", "good morning", "good afternoon", "good evening",
               "hi", "hello", "hey", "thanks", "thank you",
               "help", "what can you do", "who are you", "how are you"}:
        return {"route": "conversation"}

    if low in {"exit", "quit", "q", "bye"}:
        return {"route": "exit"}

    # Policy intent has priority over generic words such as "explain".
    policy_phrases = (
        "cpcb", "naaqs", "na aqs", "national ambient air quality",
        "standard", "standards", "regulation", "regulations",
        "policy", "policies", "guideline", "guidelines", "compliance",
        "legal limit", "legal limits", "emission standard",
        "emission standards", "road dust", "construction dust",
        "open burning", "air act", "environmental compliance",
    )
    if any(term in normalized for term in policy_phrases):
        return {"route": "rag"}

    # Phase 1 priority fix: detect live AQI before conceptual vocabulary.
    live_time_markers = (
        "right now", "at the moment", "currently", "current", "live",
    )
    live_subject_markers = (
        "aqi", "air quality index", "air quality",
        "pollution level", "pollution levels",
        "current pm2.5", "current pm10",
    )
    if (
        any(term in normalized for term in live_time_markers)
        and any(term in normalized for term in live_subject_markers)
    ):
        return {"route": "weather"}

    # Educational questions explain a concept; they should not execute
    # DBSCAN or forecast analysis just because those terms appear.
    educational_prefixes = (
        "what is ", "what are ", "define ", "definition of ",
        "meaning of ", "explain ", "please explain ",
        "can you explain ", "could you explain ",
        "tell me about ", "describe ", "how does ", "how do ",
        "what does ", "give me a beginner explanation of ",
        "give me a simple explanation of ", "help me understand ",
        "help me to explain ", "teach me about ",
        "i want to understand ", "i would like to understand ",
        "i need you to explain ", "for my project explain ",
        "i would like to explain ", "i want to explain ",
    )
    educational_concepts = (
        "dbscan", "pollution forecasting", "air quality index",
        "aqi", "pm2.5", "pm 2.5", "pm25", "pm10", "pm 10",
        "shap", "machine learning", "particulate matter",
        "temperature inversion", "greenhouse gases",
        "nitrogen dioxide", "sulfur dioxide", "sulphur dioxide",
        "carbon monoxide", "ozone", "smog", "weatherapi",
        "air quality monitoring",
    )
    educational_style = (
        normalized.startswith(educational_prefixes)
        or "in simple words" in normalized
        or "in simple terms" in normalized
        or "for beginners" in normalized
        or "beginner explanation" in normalized
        or "for a student" in normalized
        or "stands for" in normalized
        or "what is meant by" in normalized
        or "how it works" in normalized
    )
    # Model-specific SHAP/feature-importance questions are analysis requests,
    # not basic concept explanations.
    model_analysis_terms = (
        "feature importance", "shap values", "shap analysis",
        "shap explanation", "shap results", "explain the model",
        "explain model output", "explain the prediction",
        "why did the model", "why did prediction",
        "model interpretability",
    )
    if any(term in normalized for term in model_analysis_terms):
        return {"route": "forecast_shap"}

    if (
        educational_style
        and any(term in normalized for term in educational_concepts)
    ):
        return {"route": "conceptual"}

    # Specific hotspot operations must win over incidental words like
    # "currently" or "next 24 hours".
    hotspot_phrases = (
        "hotspot", "hotspots", "hot spot", "hot spots",
        "dbscan", "clustering", "pollution cluster", "pollution clusters",
        "identify polluted zone", "identify polluted zones",
        "identify polluted area", "identify polluted areas",
        "find polluted zone", "find polluted zones",
        "find polluted area", "find polluted areas",
        "detect polluted zone", "detect polluted zones",
        "detect high pollution zone", "detect high pollution zones",
        "high pollution zone", "high pollution zones",
        "identify high pollution", "find high pollution",
        "locate pollution hotspot", "locate pollution hotspots",
        "show polluted zones", "show polluted areas",
        "most polluted location", "most polluted locations",
        "most polluted area", "most polluted areas",
        "which areas are the most polluted",
        "which area is the most polluted",
        "where is pollution highest", "where is pollution worst",
        "worst polluted areas", "worst pollution areas",
        "areas with highest pollution", "areas with high pollution",
        "spatial analysis", "polluted zone", "polluted area",
    )
    if any(term in normalized for term in hotspot_phrases):
        return {"route": "dbscan"}

    # Current/live AQI takes priority over a time-window phrase added to
    # the same sentence (for example, "current AQI for the next 24 hours").
    live_aqi_phrases = (
        "current aqi", "currently aqi", "live aqi",
        "current air quality", "air quality right now",
        "current pollution", "current pm2.5", "current pm10",
        "check the aqi", "check aqi", "check air quality",
        "show current aqi", "get the aqi", "get aqi",
        "how polluted is", "how polluted are",
        "how clean is the air", "pollution level currently",
        "pollution levels currently",
    )
    if any(term in normalized for term in live_aqi_phrases):
        return {"route": "weather"}

    # Explicit prediction/forecast verbs should win over general pollution
    # vocabulary, but not over a direct current-AQI request.
    forecast_phrases = (
        "predict", "prediction", "predicting", "forecast", "forecasting",
        "xgboost", "tomorrow pm2.5", "future pm2.5",
        "future pollution", "next hour", "next 1 hour",
        "next 24 hours", "next 24 hour", "predict pollution",
        "predict the pollution", "predict pollution level",
        "predict pollution levels", "forecast pollution",
        "forecast the pollution", "forecast pollution level",
        "forecast pollution levels", "predict air quality",
        "forecast air quality", "predict pm", "forecast pm",
        "predict aqi", "forecast aqi", "tomorrow pollution",
        "tomorrow's pollution",
    )
    if any(term in normalized for term in forecast_phrases):
        return {"route": "forecast_shap"}

    # Explain the actual model output/feature importance => analysis.
    # "What is SHAP?" or "Explain SHAP" without a model-analysis request
    # remains conceptual.
    shap_analysis_phrases = (
        "feature importance", "shap values", "shap analysis",
        "shap explanation", "shap results", "explain the model",
        "explain model output", "explain the prediction",
        "why did the model", "why did prediction",
        "model interpretability",
    )
    if any(term in normalized for term in shap_analysis_phrases):
        return {"route": "forecast_shap"}

    # Only route an explanation to conceptual when it concerns a supported
    # environmental/AI concept. "What is the capital of France?" is general
    # conversation, not an environmental concept question.
    concept_terms = (
        "aqi", "air quality index", "pm2.5", "pm 2.5", "pm25",
        "pm10", "pm 10", "ozone", "nitrogen dioxide", "no2",
        "sulfur dioxide", "sulphur dioxide", "so2", "carbon monoxide",
        "smog", "air pollution", "weatherapi", "dbscan", "shap",
        "machine learning", "air quality monitoring",
        "pollution forecasting", "particulate matter",
        "temperature inversion", "greenhouse gases",
        "vehicle emissions", "industrial pollution",
        "air quality sensors", "weather", "pollutant",
        "pollution", "emission", "emissions",
    )
    conceptual_prefixes = (
        "what is ", "what are ", "who is ", "define ",
        "definition of ", "meaning of ", "explain ",
        "can you explain ", "could you explain ",
        "please explain ", "tell me about ",
        "can you tell me about ", "describe ",
        "how does ", "how do ", "why does ", "why do ",
        "what does ", "what do ", "difference between ",
        "give me a beginner explanation of ",
        "give me a simple explanation of ",
        "help me understand ", "teach me about ",
        "i want to understand ", "i would like to understand ",
        "i want to learn about ", "i would like to learn about ",
        "i need you to explain ", "for my project explain ",
        "help me to explain ", "i would like to explain ",
        "i want to explain ",
    )
    conceptual_style = (
        normalized.startswith(conceptual_prefixes)
        or "in simple words" in normalized
        or "in simple terms" in normalized
        or "for beginners" in normalized
        or "beginner explanation" in normalized
        or "full form of" in normalized
        or "stands for" in normalized
        or "what is meant by" in normalized
        or "how it works" in normalized
    )
    has_concept = any(term in normalized for term in concept_terms)

    # Weather-specific questions should go to weather even when phrased as
    # requests for current values without using the literal word "AQI".
    weather_phrases = (
        "weather", "temperature", "rain", "rainfall", "humidity",
        "wind speed", "wind direction", "will it rain",
    )
    if any(term in normalized for term in weather_phrases):
        # "What is weather?" is conceptual; a weather lookup is operational.
        if not conceptual_style or any(term in normalized for term in (
            "current", "currently", "today", "tomorrow", "right now",
            "check", "show me", "get ", "fetch ", "forecast",
        )):
            return {"route": "weather"}

    if conceptual_style and has_concept:
        return {"route": "conceptual"}

    # Remaining environmental lookup phrasing.
    if _has_term(low, LIVE_AQI_TERMS):
        return {"route": "weather"}

    if _has_term(low, WEATHER_TERMS):
        return {"route": "weather"}

    return {"route": "conversation"}

def weather_node(state):

    question = state.get(
        "question",
        ""
    )

    try:

        result = get_environment_for_user(
            question
        )

    except Exception as exc:

        result = {
            "status": "degraded",
            "location": {
                "requested_location": "Pune",
                "weatherapi_location": "Pune",
            },
            "current": {},
            "current_aqi": {},
            "forecast_24_hours": [],
            "prediction": {
                "pm25_next_1h": None,
                "label": "Unavailable",
            },
            "policy": [
                f"Environmental service unavailable: {exc}"
            ],
            "recommendations": [],
        }

    return {
        "environment": result
    }


def rag_node(state):

    question = state.get(
        "question",
        ""
    )

    try:

        result = answer_question(
            question
        )

    except Exception as exc:

        result = {
            "answer":
                "RAG policy service is temporarily unavailable.",
            "error":
                str(exc),
        }

    return {
        "rag": result
    }


def dbscan_node(state):
    """Run the canonical spatial clustering service without fabricated fallback data."""
    question = state.get("question", "")
    requested_location = _extract_location_from_question(question)
    location_key = str(requested_location or "Pune").strip().casefold()

    if location_key not in {"pune", "pune city", "pune metropolitan area"}:
        return {
            "dbscan": {
                "requested_location": requested_location,
                "stations": [],
                "hotspot_count": 0,
                "cluster_count": 0,
                "hyperparameters": "Haversine distance, eps=5 km, min_samples=2",
                "available": False,
                "status": "UNSUPPORTED_HOTSPOT_COVERAGE",
                "message": (
                    "DBSCAN hotspot analysis is validated only for Pune. "
                    "No Pune results are presented as results for another locality."
                ),
            }
        }

    try:
        from backend.ml.dbscan.hotspot_detection import get_hotspot_clusters

        records = get_hotspot_clusters(eps_km=5.0, min_samples=2)
        stations = []

        for row in records:
            pm25 = float(row["pm25_mean"])
            cluster = int(row["cluster"])
            is_clustered = bool(row["is_hotspot_cluster"])
            is_hotspot = bool(row["is_pollution_hotspot"])

            if is_hotspot and pm25 >= 120:
                category = "Critical Hotspot"
            elif is_hotspot and pm25 >= 90:
                category = "Severe Hotspot"
            elif is_hotspot:
                category = "Pollution Hotspot"
            elif pm25 >= 60:
                category = "Elevated"
            else:
                category = "Moderate / Lower"

            stations.append({
                "station": str(row["station_name"]).replace("_", " ").strip(),
                "pm25": pm25,
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "category": category,
                "cluster": cluster,
                "is_hotspot_cluster": is_clustered,
                "is_pollution_hotspot": is_hotspot,
                "observations": int(row.get("observations", 0)),
            })

        stations.sort(key=lambda station: station["pm25"], reverse=True)
        cluster_ids = {
            station["cluster"]
            for station in stations
            if station["cluster"] != -1
        }

        return {
            "dbscan": {
                "requested_location": "Pune",
                "stations": stations,
                "hotspot_count": sum(
                    station["is_pollution_hotspot"] for station in stations
                ),
                "cluster_count": len(cluster_ids),
                "hyperparameters": "Haversine distance, eps=5 km, min_samples=2",
                "available": bool(stations),
                "status": "OK" if stations else "NO_STATION_RESULTS",
                "message": (
                    "PM2.5 figures are processed-dataset means, not confirmed live readings."
                ),
            }
        }
    except Exception as exc:
        return {
            "dbscan": {
                "requested_location": "Pune",
                "stations": [],
                "hotspot_count": 0,
                "cluster_count": 0,
                "hyperparameters": "Haversine distance, eps=5 km, min_samples=2",
                "available": False,
                "status": "DBSCAN_EXECUTION_FAILED",
                "message": "DBSCAN could not produce validated results: " + str(exc),
            }
        }


def forecast_shap_node(state):
    question = state.get("question", "")
    requested_location = _extract_location_from_question(question)

    try:
        from backend.services.forecast_service import get_canonical_forecast

        forecast_res = get_canonical_forecast(requested_location)
        case = forecast_res.get("case", "CASE_C")
        forecast_avail = forecast_res.get("forecast_available", False)
        shap_res = forecast_res.get("shap_explanation") or {}

        return {
            "forecast_shap": {
                "success": True,
                "case": case,
                "forecast_available": forecast_avail,
                "requested_location": requested_location,
                "resolved_location": forecast_res.get("resolved_location"),
                "forecast_method": forecast_res.get("forecast_method"),
                "forecast_method_label": forecast_res.get("forecast_method_label", "Unavailable"),
                "is_spatial_estimate": forecast_res.get("is_spatial_estimate", False),
                "predicted_pm25": forecast_res.get("predicted_pm25"),
                "unit": forecast_res.get("unit", "µg/m³"),
                "model": "Multi-Station XGBoost Regressor (Tree-based ensemble)",
                "reason": forecast_res.get("reason"),
                "contributing_stations": forecast_res.get("contributing_stations", []),
                "shap_expected_value": shap_res.get("expected_value"),
                "shap_features": shap_res.get("features", [])[:10],
            }
        }
    except Exception as exc:
        return {
            "forecast_shap": {
                "success": False,
                "error": str(exc),
                "requested_location": requested_location,
            }
        }


def _fmt(value):

    if value is None:
        return "Unavailable"

    if value == "":
        return "Unavailable"

    return str(value)


def final_node(state):

    route = state.get(
        "route",
        "weather"
    )

    if route == "exit":

        return {
            "final_answer": "Goodbye."
        }

    if route == "conversation":
        question = str(state.get("question", "")).strip().lower()

        if question in {"hi", "hello", "hey", "good morning",
                        "good afternoon", "good evening"}:
            answer = (
                "Hello! I'm ORIVA, your environmental intelligence "
                "assistant. Ask me about AQI, weather, pollution hotspots, "
                "pollution forecasts, or environmental policy."
            )
        elif question in {"thanks", "thank you"}:
            answer = "You're welcome! Ask me an environmental question anytime."
        elif question in {"help", "what can you do", "who are you"}:
            answer = (
                "I can explain environmental concepts, retrieve available "
                "weather/AQI data, analyze supported hotspots, run supported "
                "forecasts, and answer environmental policy questions."
            )
        else:
            answer = (
                "I couldn't confidently match that question to a supported "
                "environmental task. Try asking about AQI, weather, hotspots, "
                "forecasts, or environmental policy."
            )

        return {"final_answer": answer}

    if route == "rag":

        result = state.get(
            "rag"
        )

        if isinstance(
            result,
            dict
        ):

            lines = [
                "POLICY / RAG ANSWER",
                "=" * 78,
                str(
                    result.get(
                        "answer",
                        result
                    )
                ),
            ]

            sources = (
                result.get(
                    "sources"
                )
                or []
            )

            if sources:

                lines.extend([
                    "",
                    "SOURCES",
                    "-" * 78,
                ])

                lines.extend(
                    f"- {source}"
                    for source in sources
                )

            return {
                "final_answer":
                    "\n".join(lines)
            }

        return {
            "final_answer":
                str(result)
        }

    if route == "dbscan":
        db = state.get("dbscan") or {}
        req_loc = db.get("requested_location", "Pune")
        stations = db.get("stations", [])

        if not db.get("available", True):
            return {
                "final_answer": "\n".join([
                    "DBSCAN SPATIAL HOTSPOT REPORT",
                    "=" * 78,
                    f"Requested location: {req_loc}",
                    f"Status: {db.get('status', 'UNAVAILABLE')}",
                    str(db.get("message") or "No validated results are available."),
                ])
            }

        matched_station = None
        if req_loc.lower() != "pune":
            for s in stations:
                if req_loc.lower() in s["station"].lower() or s["station"].lower() in req_loc.lower():
                    matched_station = s
                    break

        lines = [
            "DBSCAN SPATIAL HOTSPOT & CLUSTERING REPORT",
            "=" * 78,
            f"Target Region: {req_loc if req_loc != 'Pune' else 'Pune Metropolitan Area'}",
            "Clustering Algorithm: DBSCAN (Density-Based Spatial Clustering of Applications with Noise)",
            f"Hyperparameters: {db.get('hyperparameters', 'Haversine distance, eps=5 km, min_samples=2')}",
            f"Total Monitored Stations: {len(stations)}",
            f"Identified Hotspot Stations: {db.get('hotspot_count', 0)}",
            "",
        ]

        if matched_station:
            lines.extend([
                f"SPECIFIC LOCALITY STATUS: {matched_station['station']}",
                "-" * 78,
                f"Processed-dataset mean PM2.5: {matched_station['pm25']:.1f} µg/m³",
                f"Hotspot Classification: {matched_station['category'].upper()}",
                f"Coordinates: {matched_station['latitude']:.4f}, {matched_station['longitude']:.4f}",
                f"Spatial Cluster: Cluster {matched_station['cluster']}" if matched_station['cluster'] != -1 else "Spatial Cluster: Isolated / Boundary Station",
                "",
            ])

        lines.extend([
            "ALL STATIONS & SPATIAL CLUSTERS (RANKED BY PROCESSED-DATASET MEAN PM2.5)",
            "-" * 78,
            "Metric: Processed-dataset mean PM2.5; these are not confirmed live readings.",
        ])

        for i, s in enumerate(stations, start=1):
            display_name = str(s["station"]).replace("_", " ").strip()
            cluster_id = int(s.get("cluster", -1))
            spatial_status = (
                f"Cluster {cluster_id}" if cluster_id != -1 else "Isolated"
            )
            pollution_status = (
                "Pollution hotspot"
                if s.get("is_pollution_hotspot", False)
                else s["category"]
            )
            lines.append(
                f"{i:2d}. {display_name:<26} | PM2.5 mean: {s['pm25']:>6.1f} | "
                f"Spatial: {spatial_status:<10} | Pollution: {pollution_status}"
            )
            lines.append(
                f"    Coordinates: ({s['latitude']:.4f}, {s['longitude']:.4f})"
            )

        lines.extend([
            "",
            "HOTSPOT MITIGATION & POLICY MEASURES (CPCB / MPCB)",
            "-" * 78,
            "1. Targeted wet-dust suppression & mechanized road sweeping on major access corridors.",
            "2. Intensive vehicle emission compliance & anti-idling enforcement around hotspot junctions.",
            "3. Stricter C&D (construction & demolition) green-netting and water-misting enforcement.",
            "4. Continuous 24/7 localized sensor monitoring to detect abnormal industrial or biomass spikes.",
        ])

        return {"final_answer": "\n".join(lines)}

    if route == "forecast_shap":
        fs = state.get("forecast_shap") or {}
        if not fs.get("success"):
            return {
                "final_answer": f"Forecast/SHAP Error: {fs.get('error', 'Unable to generate forecast.')}"
            }

        case = fs.get("case", "CASE_C")
        req_loc = fs.get("requested_location", "Unknown")
        resolved_loc = fs.get("resolved_location", req_loc)

        if case == "CASE_C" or not fs.get("forecast_available"):
            lines = [
                "XGBOOST PM2.5 FORECAST & SHAP REPORT (DATA COVERAGE NOTICE)",
                "=" * 78,
                f"Target Location: {req_loc}",
                f"Geocoded Location: {resolved_loc}",
                "Status: FORECAST SUPPRESSED (CASE C — INSUFFICIENT LOCAL CPCB DATA)",
                "-" * 78,
                "",
                "REASON FOR SUPPRESSION:",
                f"{fs.get('reason')}",
                "",
                "DATA INTEGRITY SAFEGUARD:",
                "The AI Pollution System enforces transparent geographic constraints. We do not",
                "substitute distant station observations or fabricate numerical predictions when",
                "reliable ground monitoring stations are unavailable within 50 km.",
            ]
            return {"final_answer": "\n".join(lines)}

        method_label = fs.get("forecast_method_label", "Station Forecast")
        is_spatial = fs.get("is_spatial_estimate", False)

        lines = [
            "XGBOOST PM2.5 FORECAST & SHAP EXPLAINABILITY REPORT",
            "=" * 78,
            f"Target Location: {req_loc}",
            f"Resolved Location: {resolved_loc}",
            f"Forecast Strategy: {case} — {method_label}",
            f"Model Architecture: {fs.get('model', 'Multi-Station XGBoost Regressor')}",
            f"Forecast Horizon: Next 1 Hour",
            "",
            "XGBOOST FORECAST PREDICTION",
            "-" * 78,
            f"Predicted Next-Hour PM2.5: {fs.get('predicted_pm25')} {fs.get('unit')}",
            f"Baseline Expected Value (E[y]): {fs.get('shap_expected_value', 0)} {fs.get('unit')}",
            f"Classification: {'SPATIALLY ESTIMATED FORECAST' if is_spatial else 'DIRECT CPCB IN-SITU FORECAST'}",
            "",
            "CONTRIBUTING MONITORING STATIONS",
            "-" * 78,
        ]

        for st in fs.get("contributing_stations", []):
            lines.append(
                f"- {st['clean_name']:<20} | Dist: {st['distance_km']:>5.2f} km | Weight: {st.get('weight', 1.0):>5.1%} | Observed: {st.get('observed_pm25', 'N/A')} µg/m³"
            )

        lines.extend([
            "",
            "SHAP ATTRIBUTION BREAKDOWN (TreeExplainer)",
            "-" * 78,
            "Exact additive feature contributions pushing the prediction higher (+) or lower (-):",
            "",
        ])

        for i, f in enumerate(fs.get("shap_features", []), start=1):
            val = f.get("feature_value")
            val_str = f"{val:.2f}" if isinstance(val, float) else str(val)
            lines.append(
                f"{i:2d}. {f['feature']:<24} | SHAP: {f['shap_value']:>+8.4f} | Observed: {val_str:<8} | {f['effect']}"
            )

        lines.extend([
            "",
            "MODEL INTERPRETABILITY INSIGHT",
            "-" * 78,
            f"- Primary Driving Factor: {fs.get('shap_features', [{}])[0].get('feature', 'pm25')}",
            "- SHAP Explanation Note: SHAP quantifies statistical feature attributions of the model;",
            "  it reflects learned associations rather than physical causal proof.",
        ])

        return {"final_answer": "\n".join(lines)}

    data = (
        state.get(
            "environment"
        )
        or {}
    )

    loc = (
        data.get(
            "location"
        )
        or {}
    )

    current = (
        data.get(
            "current"
        )
        or {}
    )

    aqi = (
        data.get(
            "current_aqi"
        )
        or {}
    )

    prediction = (
        data.get(
            "prediction"
        )
        or {}
    )

    hourly = (
        data.get(
            "forecast_24_hours"
        )
        or []
    )

    policy = (
        data.get(
            "policy"
        )
        or []
    )

    recommendations = (
        data.get(
            "recommendations"
        )
        or []
    )

    provenance = (
        data.get(
            "data_provenance"
        )
        or {}
    )

    req_loc = loc.get("requested_location") or "Pune"
    disp_loc = loc.get("display_name") or req_loc
    if req_loc.lower() != "pune" and req_loc.lower() not in disp_loc.lower():
        disp_loc = f"{req_loc}, {loc.get('region', 'Maharashtra')}"

    lines = [
        "AI ENVIRONMENTAL INTELLIGENCE REPORT",
        "=" * 78,

        f"Location: {disp_loc}",

        f"Region: {_fmt(loc.get('region'))}",

        f"Coordinates: {_fmt(loc.get('latitude'))}, {_fmt(loc.get('longitude'))}",

        f"Timezone: {_fmt(loc.get('timezone'))}",

        f"Local time: {_fmt(loc.get('local_time'))}",

        "",

        "CURRENT CONDITIONS",

        "-" * 78,
    ]

    fields = [
        ("PM2.5", "pm2_5", "µg/m³"),
        ("PM10", "pm10", "µg/m³"),
        ("NO2", "no2", "µg/m³"),
        ("SO2", "so2", "µg/m³"),
        ("CO", "co", "µg/m³"),
        ("O3", "o3", "µg/m³"),
        ("Temperature", "temperature_c", "°C"),
        ("Feels Like", "feels_like_c", "°C"),
        ("Humidity", "humidity", "%"),
        ("Rainfall", "rainfall_mm", "mm"),
        ("Wind", "wind_speed_kph", "km/h"),
        ("Wind Direction", "wind_direction", ""),
        ("Visibility", "visibility_km", "km"),
        ("UV", "uv", ""),
        ("Condition", "condition", ""),
    ]

    for label, key, unit in fields:

        value = current.get(
            key
        )

        if value is not None:

            if isinstance(
                value,
                float
            ):
                text = f"{value:.1f}"
            else:
                text = str(value)

            if unit:
                text = f"{text} {unit}"

            lines.append(
                f"{label}: {text}"
            )

    lines.extend([
        "",
        "CURRENT AIR QUALITY",
        "-" * 78,
        f"Indicative AQI: {_fmt(aqi.get('value'))}",
        f"AQI category: {_fmt(aqi.get('category'))}",
        f"Controlling pollutant: {_fmt(aqi.get('controlling_pollutant') or aqi.get('pollutant'))}",
        f"AQI basis: {_fmt(aqi.get('basis') or 'Basis unavailable; interpret AQI as indicative.')}",
        "Note: This is an indicative estimate, not an official CPCB station AQI.",
    ])

    lines.extend([
        "",
        "NEXT-HOUR PM2.5",
        "-" * 78,
    ])

    pred_val = prediction.get(
        "pm25_next_1h"
    )

    if pred_val is not None:

        lines.extend([
            f"Estimated PM2.5: {pred_val:.1f} µg/m³",
            f"Trend: {_fmt(prediction.get('label'))}",
            f"Source: {_fmt(prediction.get('source'))}",
        ])

    else:

        lines.extend([
            "Estimated PM2.5: Unavailable",
            "Trend: Unavailable",
        ])

    lines.extend([
        "",
        "24-HOUR HOURLY OUTLOOK",
        "-" * 78,
    ])

    if hourly:

        for item in hourly:

            time_str = _fmt(
                item.get("time")
            )

            pm = item.get(
                "pm2_5_estimate"
            )

            pm_text = (
                f"{pm:.1f}"
                if pm is not None
                else "Unavailable"
            )

            aqi_item = (
                item.get("aqi")
                or item.get("indicative_aqi")
                or {}
            )

            aqi_val = _fmt(
                aqi_item.get("value")
            )

            cat = _fmt(
                aqi_item.get("category")
            )

            temp = (
                item.get("temp_c")
                if item.get("temp_c") is not None
                else item.get("temperature_c")
            )

            temp_text = (
                f"{temp:.1f}°C"
                if temp is not None
                else "Unavailable"
            )

            hum = item.get(
                "humidity"
            )

            hum_text = (
                f"{hum:.1f}%"
                if hum is not None
                else "Unavailable"
            )

            wind = (
                item.get("wind_kph")
                if item.get("wind_kph") is not None
                else item.get("wind_speed_kph")
            )

            wind_text = (
                f"{wind:.1f} km/h"
                if wind is not None
                else "Unavailable"
            )

            rain = (
                item.get("chance_of_rain")
                if item.get("chance_of_rain") is not None
                else item.get("rain_probability")
            )

            rain_text = (
                f"{rain:.0f}%"
                if rain is not None
                else "0%"
            )

            cond = _fmt(
                item.get("condition")
            )

            lines.append(
                f"{time_str} | PM2.5={pm_text} | "
                f"AQI={aqi_val} ({cat}) | "
                f"Temp={temp_text} | "
                f"Humidity={hum_text} | "
                f"Wind={wind_text} | "
                f"Rain={rain_text} | "
                f"{cond}"
            )

    else:

        lines.append(
            "Hourly outlook unavailable."
        )

    lines.extend([
        "",
        "WEATHER / POLLUTION POLICY ACTIONS",
        "-" * 78,
    ])

    if policy:

        lines.extend(
            f"- {action}"
            for action in policy
        )

    else:

        lines.append(
            "- No specific policy actions."
        )

    lines.extend([
        "",
        "ACTIVE RECOMMENDATIONS",
        "-" * 78,
    ])

    if recommendations:

        lines.extend(
            f"- {rec}"
            for rec in recommendations
        )

    else:

        lines.append(
            "- Continue routine environmental monitoring."
        )

    lines.extend([
        "",
        "DATA PROVENANCE",
        "-" * 78,
        f"Primary source: {_fmt(provenance.get('primary_source'))}",
        f"Location source: {_fmt(provenance.get('location_source'))}",
        f"Air-quality source: {_fmt(provenance.get('air_quality_source'))}",
        f"Forecast source: {_fmt(provenance.get('forecast_source'))}",
        f"Hourly PM2.5 source: {_fmt(provenance.get('hourly_pm25_source'))}",
        f"CPCB role: {_fmt(provenance.get('cpcb_role'))}",
        f"RAG role: {_fmt(provenance.get('rag_role'))}",
        f"LangGraph role: {_fmt(provenance.get('langgraph_role'))}",
    ])

    return {
        "final_answer":
            "\n".join(lines)
    }



def multi_agent_node(state):
    """Run requested existing specialists and combine their formatted answers."""
    handlers = {
        "weather": weather_node,
        "forecast_shap": forecast_shap_node,
        "dbscan": dbscan_node,
        "rag": rag_node,
    }
    labels = {
        "weather": "Current AQI and environment",
        "forecast_shap": "PM2.5 forecast and model analysis",
        "dbscan": "Pollution hotspots",
        "rag": "CPCB policy and standards",
    }

    sections = []
    for route in state.get("requested_routes", []):
        handler = handlers.get(route)
        if handler is None:
            continue

        substate = {
            "question": state.get("question", ""),
            "route": route,
        }
        try:
            result = handler(dict(substate))
            if isinstance(result, dict):
                substate.update(result)
            answer = str(
                final_node(substate).get("final_answer", "")
            ).strip()
            if not answer:
                answer = "This specialist returned no report."
        except Exception as exc:
            answer = (
                "This specialist could not complete its part. "
                f"Error: {type(exc).__name__}: {exc}"
            )
        sections.append(f"## {labels[route]}\n\n{answer}")

    if not sections:
        return {
            "final_answer": (
                "No specialist could be selected for this request. "
                "Please specify the environmental tasks you need."
            )
        }

    return {
        "final_answer": (
            "ORIVA MULTI-AGENT ENVIRONMENTAL REPORT\n\n"
            + "\n\n---\n\n".join(sections)
        )
    }


def route_after_intent(state):

    return state.get(
        "route",
        "weather"
    )


graph = StateGraph(
    FinalState
)

graph.add_node(
    "intent",
    intent_node
)

graph.add_node(
    "multi_agent",
    multi_agent_node
)

graph.add_node(
    "weather",
    weather_node
)

graph.add_node(
    "rag",
    rag_node
)

graph.add_node(
    "dbscan",
    dbscan_node
)

graph.add_node(
    "forecast_shap",
    forecast_shap_node
)

graph.add_node(
    "final",
    final_node
)

graph.add_edge(
    START,
    "intent"
)

graph.add_conditional_edges(
    "intent",
    route_after_intent,
    {
        "weather":
            "weather",
        "multi_agent":
            "multi_agent",
        "rag":
            "rag",
        "conceptual":
            "rag",
        "conversation":
            "final",
        "dbscan":
            "dbscan",
        "forecast_shap":
            "forecast_shap",
        "exit":
            END,
    },
)

graph.add_edge(
    "weather",
    "final"
)

graph.add_edge(
    "rag",
    "final"
)

graph.add_edge(
    "dbscan",
    "final"
)

graph.add_edge(
    "forecast_shap",
    "final"
)

graph.add_edge(
    "multi_agent",
    END
)

graph.add_edge(
    "final",
    END
)

app = graph.compile()
