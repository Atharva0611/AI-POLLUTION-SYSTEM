"""
Orchestrator — Enhanced Multi-Agent LangGraph Pipeline
======================================================
Unified stateful pipeline routing all 16 intents to specialized nodes:
- input_validation / conversation / help / unsupported
- conceptual_definition (knowledge base)
- comparison (multi-city side-by-side)
- live_aqi & weather (WeatherAPI)
- forecast & shap (Canonical Forecast Service)
- dbscan (Hotspot Clustering)
- cpcb (Station Readings)
- policy_rag (RAG Policy Retrieval)
- recommendation (Mitigation Advice)
"""

from typing import Any, Dict, List, Optional
import re
from langgraph.graph import StateGraph, START, END

from backend.agents.state import PollutionState
from backend.services.intent_router import classify_intent, extract_location
from backend.services.input_validator import validate_user_input
from backend.services.conceptual_knowledge import get_conceptual_explanation
from backend.services.comparison_service import compare_air_quality
from backend.services.location_extractor import (
    extract_single_location,
    extract_comparison_locations,
)
from backend.services.india_environment import get_environment_for_user
from backend.services.forecast_service import get_canonical_forecast
from backend.agents.policy_agent import answer_question
from backend.services.conversation_memory import SESSION_MEMORY


# ============================================================
# NODE 1 — Intent & Location Preprocessing Node
# ============================================================

def resolve_followup_context(question: str, session_memory, memory_locations=None):
    """Resolve clear short follow-ups using only this session's previous turn."""
    text = str(question or "").strip()
    history = session_memory.get_history()
    if not history:
        return None

    # Only short, explicit context-dependent phrases qualify.
    followup_patterns = (
        r"what about (?:tomorrow|today|there|that|it|the same|next week)\??",
        r"(?:and )?tomorrow\??",
        r"explain (?:that|the previous|this) (?:forecast|prediction|result)\??",
        r"(?:explain|elaborate on) that\??",
        r"what does that mean\??",
        r"why is that\??",
        r"tell me more about that\??",
    )
    if not any(re.fullmatch(pattern, text, flags=re.IGNORECASE) for pattern in followup_patterns):
        return None

    previous = history[-1].get("user", "").strip()
    if not previous:
        return None

    is_tomorrow_followup = bool(
        re.fullmatch(r"(?:what about )?tomorrow\\??", text, flags=re.IGNORECASE)
    )

    previous_intent = classify_intent(
        previous, memory_locations=memory_locations or []
    )

    # A temporal follow-up should continue the most recent relevant
    # air-quality/forecast task, not an intervening policy question.
    if is_tomorrow_followup and previous_intent not in {
        "live_aqi", "weather", "forecast"
    }:
        for turn in reversed(history):
            candidate = str(turn.get("user", "") or "").strip()
            if not candidate:
                continue
            candidate_intent = classify_intent(
                candidate, memory_locations=memory_locations or []
            )
            if candidate_intent in {"live_aqi", "weather", "forecast"}:
                previous = candidate
                previous_intent = candidate_intent
                break
        else:
            return None

    allowed = {
        "live_aqi", "weather", "forecast", "shap", "dbscan",
        "policy_rag", "cpcb", "historical_data", "source_analysis",
        "recommendation", "comparison",
    }
    if previous_intent not in allowed:
        return None

    # Preserve the previous task as context for downstream specialists.
    return {
        "intent": previous_intent,
        "contextual_question": (
            f"Previous user request: {previous}\n"
            f"Current follow-up: {text}"
        ),
    }


def intent_node(state: dict) -> dict:
    question = state.get("question", "")
    session_memory = SESSION_MEMORY.get_session(state.get('session_id'))
    recent_locs = session_memory.get_recent_locations()
    last_loc = session_memory.get_last_location()

    # Pre-validate input
    val = validate_user_input(question)
    if not val["valid"]:
        return {
            "intent": val["type"],
            "location": last_loc,
            "direct_message": val["message"],
        }

    # Conceptual check
    concept = get_conceptual_explanation(question)
    if concept:
        return {
            "intent": "pollutant_information",
            "location": last_loc,
            "direct_message": concept,
        }

    followup = resolve_followup_context(
        question, session_memory, memory_locations=recent_locs
    )
    intent = (
        followup["intent"] if followup
        else classify_intent(question, memory_locations=recent_locs)
    )
    previous_question = session_memory.get_history()[-1].get("user", "") if followup else ""
    single_loc = extract_single_location(question, fallback_memory=last_loc) or "Pune"
    comp_locs = extract_comparison_locations(question, memory_locations=recent_locs)

    direct_msg = None
    if intent == "unsupported":
        direct_msg = (
            "I specialize strictly in air pollution monitoring, forecasting, and environmental policy in India.\n"
            "I cannot assist with unrelated queries such as general trivia, stock prices, or entertainment.\n\n"
            "Please ask an environmental or pollution-related question, for example:\n"
            "• 'What is the current AQI of Mumbai?'\n"
            "• 'What is the NAAQS standard for PM10?'\n"
            "• 'Explain what PM2.5 is.'\n"
            "• 'Show pollution hotspots in Pune.'"
        )
    elif intent == "clarification_required":
        direct_msg = "Please enter a pollution-related question."

    return {
        "intent": intent,
        "question": question,
        "previous_question": previous_question,
        "is_followup": bool(followup),
        "location": single_loc,
        "comparison_locations": comp_locs,
        "direct_message": direct_msg,
        "requested_intents": detect_multi_agent_intents(question, intent),
    }


# ============================================================
# NODE 2a — Direct Conversational Node (Greetings, Help, Out-of-Domain)
# ============================================================


def detect_multi_agent_intents(question: str, primary_intent: str) -> list:
    """Detect multiple explicit specialist tasks without changing single routes."""
    if primary_intent in {
        "comparison", "greeting", "conversation", "farewell", "gratitude",
        "help", "empty", "numeric", "unsupported", "conceptual_definition",
        "pollutant_information", "clarification_required"
    }:
        return []

    q = str(question or "").casefold()
    patterns = {
        "live_aqi": (
            r"\b(?:current|live|real[- ]time)\b.{0,45}"
            r"\b(?:aqi|air quality|pollution|pm2\.?5|pm10)\b",
            r"\b(?:weather|temperature|humidity|rainfall|wind speed|wind direction)\b",
            r"\b(?:aqi|air quality)\b.{0,30}\b(?:right now|currently|today)\b",
            r"\b(?:combined report|report covering|covering)\b.{0,45}\b(?:aqi|air quality)\b",
        ),
        "forecast": (
            r"\b(?:forecast|predict(?:ion)?|next hour|tomorrow|projected)\b",
            r"\bfuture\s+(?:aqi|pollution|pm2\.?5)\b",
        ),
        "shap": (
            r"\bshap\b", r"\bshapley\b", r"\bfeature attribution\b",
            r"\bfeature importance\b",
            r"\bexplain\s+(?:the\s+)?(?:model|prediction|forecast)\b",
        ),
        "dbscan": (
            r"\bhotspots?\b", r"\bspatial clustering\b",
            r"\bdbscan\b", r"\bcluster(?:s|ing)?\b",
        ),
        "policy_rag": (
            r"\bnaaqs\b", r"\bncap\b", r"\bgrap\b",
            r"\bregulations?\b", r"\bguidelines?\b", r"\bpolicy\b",
            r"\bpolicies\b", r"\bcompliance\b", r"\blegal limit\b",
            r"\bcpcb rules?\b",
            r"\bcpcb\b.{0,40}\b(?:standard|standards|limit|limits|guideline|guidelines|policy|policies|rule|rules|regulation|regulations)\b",
            r"\bpm\s*2\.?5\b.{0,30}\bstandards?\b",
            r"\bair act\b",
        ),
        "recommendation": (
            r"\brecommendations?\b", r"\bmitigation\b",
            r"\bwhat can be done\b", r"\bwhat steps\b",
            r"\bhow to reduce\b", r"\bsuggest(?:ions?)?\b",
            r"\baction plan\b",
        ),
    }

    requested = [
        name for name, expressions in patterns.items()
        if any(re.search(expression, q) for expression in expressions)
    ]

    # Forecast and SHAP are served by the same existing specialist.
    if "forecast" in requested or "shap" in requested:
        requested = [
            name for name in requested if name not in {"forecast", "shap"}
        ]
        requested.insert(0, "forecast")

    return requested if len(requested) >= 2 else []


def direct_node(state: dict) -> dict:
    msg = state.get("direct_message")
    if not msg:
        q = state.get("question", "")
        concept = get_conceptual_explanation(q)
        if concept:
            msg = concept
        else:
            val = validate_user_input(q)
            msg = val.get("message") or "I specialize in air pollution queries. Please ask about AQI, forecasts, hotspots, or policies."
    return {"final_answer": msg}


# ============================================================
# NODE 2b — Comparison Node (Side-by-Side Multi-City Analysis)
# ============================================================

def comparison_node(state: dict) -> dict:
    locs = state.get("comparison_locations") or []
    if len(locs) < 2:
        # Check memory
        recent = SESSION_MEMORY.get_session(
            state.get('session_id')
        ).get_recent_locations()
        if len(recent) >= 2:
            locs = recent[-2:]
        else:
            locs = ["Pune", "Mumbai"]

    answer = compare_air_quality(locs)
    return {"final_answer": answer}


# ============================================================
# NODE 2c — Live AQI & Weather Node
# ============================================================

def weather_node(state: dict) -> dict:
    question = state.get("question", "")
    location = state.get("location", "Pune")
    try:
        # The environment service extracts the requested location from the question.
        env = get_environment_for_user(question or location)
    except Exception as exc:
        env = {"status": "error", "error": str(exc)}
    return {"environment": env, "location": location}


# ============================================================
# NODE 2d — Forecast & SHAP Node
# ============================================================

def forecast_shap_node(state: dict) -> dict:
    location = state.get("location", "Pune")
    try:
        forecast_res = get_canonical_forecast(location)
    except Exception as exc:
        forecast_res = {
            "status": "error",
            "forecast_available": False,
            "case": "CASE_C",
            "reason": str(exc),
            "requested_location": location,
        }
    return {"forecast_data": forecast_res, "location": location}


# ============================================================
# NODE 2e — DBSCAN Hotspots Node
# ============================================================

def dbscan_node(state: dict) -> dict:
    """Run real DBSCAN using the processed CPCB station dataset."""

    from backend.ml.dbscan.hotspot_detection import (
        get_hotspot_clusters
    )

    location = state.get("location", "Pune")

    # The configured DBSCAN inputs contain Pune monitoring stations only.
    # Never label these results as another city's hotspot analysis.
    if str(location).strip().casefold() != "pune":
        return {
            "location": location,
            "dbscan_data": {
                "requested_location": location,
                "stations": [],
                "hotspot_count": 0,
                "cluster_count": 0,
                "available": False,
                "status": "UNSUPPORTED_HOTSPOT_COVERAGE",
                "message": (
                    "Hotspot clustering is currently validated only for Pune. "
                    "No hotspot results were generated for this location."
                ),
            },
        }

    try:
        records = get_hotspot_clusters()

        stations = []

        for row in records:
            cluster = int(row.get("cluster", -1))
            pm25 = float(row.get("pm25_mean", 0))

            if cluster == -1:
                category = "Noise / Isolated"
            elif pm25 >= 90:
                category = "Critical Hotspot"
            elif pm25 >= 60:
                category = "High Hotspot"
            else:
                category = "Clustered Station"

            stations.append({
                "station": row.get("station_name", "Unknown"),
                "pm25": pm25,
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "category": category,
                "cluster": cluster,
                "observations": int(row.get("observations", 0)),
                "pollution_level": row.get(
                    "pollution_level", "Unknown"
                ),
                "hotspot_score": float(
                    row.get("hotspot_score", 0)
                ),
            })

        cluster_ids = {
            s["cluster"] for s in stations
            if s["cluster"] != -1
        }

        hotspot_count = sum(
            1 for s in stations
            if s["cluster"] != -1
            and s["pm25"] >= 60
        )

        return {
            "dbscan_data": {
                "requested_location": location,
                "stations": stations,
                "hotspot_count": hotspot_count,
                "cluster_count": len(cluster_ids),
                "hyperparameters": (
                    "Haversine distance, eps=5 km, min_samples=2"
                ),
                "source": "Processed CPCB station dataset",
            },
            "dbscan_source": "Processed CPCB station dataset",
            "location": location,
            "error": "",
        }

    except Exception as exc:
        return {
            "dbscan_data": {
                "requested_location": location,
                "stations": [],
                "hotspot_count": 0,
                "cluster_count": 0,
            },
            "dbscan_source": "DBSCAN execution failed",
            "location": location,
            "error": str(exc),
        }


# NODE 2f — RAG Policy Node
# ============================================================

def rag_node(state: dict) -> dict:
    """Retrieve policy documents and format answer with source references."""

    question = state.get("question", "")

    try:
        result = answer_question(question)

        if isinstance(result, dict):
            answer = result.get(
                "answer",
                "No relevant information found."
            )

            sources = result.get("sources", [])

            if isinstance(answer, list):
                answer = "\n".join(
                    str(item) for item in answer
                )

            answer = str(answer).strip()

            if sources:
                source_lines = []

                for source in sources:
                    if isinstance(source, dict):
                        filename = source.get(
                            "file", "Unknown"
                        )
                        page = source.get(
                            "page", "Unknown"
                        )

                        source_lines.append(
                            f"- {filename} (page {page})"
                        )
                    else:
                        source_lines.append(
                            f"- {source}"
                        )

                answer += (
                    "\n\nRetrieved sources:\n"
                    + "\n".join(source_lines)
                )

            return {
                "policy": answer,
                "policy_success": True,
                "retrieved_documents": sources,
                "error": "",
            }

        return {
            "policy": str(result),
            "policy_success": True,
            "error": "",
        }

    except Exception as exc:
        return {
            "policy": (
                "The policy knowledge base could not "
                "complete this request."
            ),
            "policy_success": False,
            "error": str(exc),
        }


# NODE 2g — Recommendation Node
# ============================================================

def recommendation_node(state: dict) -> dict:
    location = state.get("location", "Pune")
    try:
        env = get_environment_for_user(location)
    except Exception:
        env = {}
    return {
        "environment": env,
        "recommendations": env.get("recommendations", []),
        "location": location,
    }


# ============================================================
# ROUTER
# ============================================================

def route_after_intent(state: dict) -> str:
    """Route coordinated multi-agent requests or existing single intents."""
    if len(state.get("requested_intents") or []) >= 2:
        return "multi_agent"
    intent = state.get("intent", "clarification_required")

    # These intents should return a direct response without running ML agents.
    if intent in {
        "greeting", "conversation", "farewell", "gratitude", "help",
        "empty", "numeric", "unsupported", "conceptual_definition",
        "pollutant_information", "clarification_required"
    }:
        return "direct"

    if intent == "comparison":
        return "comparison"

    if intent in {"live_aqi", "weather"}:
        return "weather"

    if intent == "forecast":
        return "forecast_shap"

    if intent == "shap":
        return "forecast_shap"

    if intent == "dbscan":
        return "dbscan"

    if intent in {
        "policy_rag", "cpcb", "historical_data",
        "source_analysis"
    }:
        return "rag"

    if intent == "recommendation":
        return "recommendation"

    # Never silently send an unknown intent to the live AQI agent.
    state["direct_message"] = (
        "I couldn't determine the requested operation. Please specify "
        "whether you want current AQI, a PM2.5 forecast, weather, "
        "hotspot clustering, model explanation, or policy information."
    )
    return "direct"


def final_node(state: dict) -> dict:
    # If direct answer already formed (direct_node, comparison_node), preserve it
    if state.get("final_answer"):
        return {"final_answer": state["final_answer"]}

    intent = state.get("intent")
    location = state.get("location", "Pune")

    # ---------------------------------------------------------
    # SOURCE ANALYSIS
    # ---------------------------------------------------------
    if intent == "source_analysis":
        lines = [
            f"AIR POLLUTION SOURCE APPORTIONMENT REPORT — {location}",
            "=" * 78,
            f"Target Location: {location}",
            "Framework: CPCB & SAFAR Comprehensive Urban Source Apportionment",
            "-" * 78,
            "",
            "ESTIMATED SECTORAL SOURCE CONTRIBUTIONS (ANNUALIZED URBAN AVERAGE)",
            "-" * 78,
            "1. Vehicular Emissions (30% – 40%):",
            "   • Heavy-duty diesel freight, idling at congested corridors, two-stroke exhaust.",
            "   • Key pollutants: NO2, Fine PM2.5, Black Carbon, Carbon Monoxide.",
            "",
            "2. Road Dust Resuspension & Construction (20% – 30%):",
            "   • Mechanical resuspension by moving traffic on unpaved berms, active C&D sites.",
            "   • Key pollutants: Coarse PM10, crustal silica, mineral dust.",
            "",
            "3. Industrial Boilers & Power Generation (15% – 20%):",
            "   • Nearby industrial estates (e.g., Bhosari, Chakan, Hadapsar), diesel generators.",
            "   • Key pollutants: SO2, NO2, chemical aerosols.",
            "",
            "4. Biomass, Stubble & Open Waste Burning (10% – 15%):",
            "   • Seasonal stubble burning, municipal garbage incineration, open leaf burning.",
            "   • Key pollutants: High PM2.5 spikes, organic carbon, toxic dioxins.",
            "",
            "5. Domestic & Secondary Atmospheric Chemistry (5% – 10%):",
            "   • LPG/solid fuel cooking, secondary aerosol formation from NH3 and VOCs.",
            "",
            "REGULATORY ACTION PLAN",
            "-" * 78,
            "Under the National Clean Air Programme (NCAP), source-targeted actions include:",
            "• End-to-end blacktopping of roads and daily mechanized sweeping with water misting.",
            "• Automated PUC enforcement and EV transition on dense public-transit corridors.",
            "• Strict geotagged monitoring against open biomass and landfill waste burning.",
        ]
        return {"final_answer": "\n".join(lines)}

    # ---------------------------------------------------------
    # CPCB & HISTORICAL DATA
    # ---------------------------------------------------------
    if intent in {"cpcb", "historical_data"}:
        lines = [
            f"CPCB CAAQMS MONITORING STATIONS & HISTORICAL DATA — {location}",
            "=" * 78,
            f"Target Region: {location}",
            "Operating Authority: Central Pollution Control Board (CPCB) / State PCB Network",
            "-" * 78,
            "",
            "CONTINUOUS AMBIENT AIR QUALITY MONITORING (CAAQMS) ARCHITECTURE",
            "-" * 78,
            "• Monitoring Method: Continuous automated beta-attenuation (PM2.5/PM10), UV fluorescence (SO2),",
            "  chemiluminescence (NO2), NDIR (CO), and UV photometry (O3).",
            "• Sampling Frequency: Continuous 15-minute telemetry aggregated into hourly averages.",
            "• Regulatory Framework: Governed by the Air (Prevention and Control of Pollution) Act, 1981.",
            "",
            "DATA RETRIEVAL & HISTORICAL BENCHMARK",
            "-" * 78,
            f"• Primary Reference Station for {location}: Continuous Real-time Monitoring Station.",
            "• Historical Trend: Elevated particulate concentrations observed during dry winter inversion (Nov–Feb),",
            "  with substantial dispersion during the southwest monsoon (June–Sept).",
            "• NAAQS 24-Hour Benchmark: PM2.5 = 60 µg/m³ | PM10 = 100 µg/m³ | NO2 = 80 µg/m³.",
            "",
            "Data Access Note: Official station historical datasets are archived via the CPCB CCR portal.",
        ]
        return {"final_answer": "\n".join(lines)}

    # ---------------------------------------------------------
    # FORECAST & SHAP
    # ---------------------------------------------------------
    if intent in {"forecast", "shap"}:
        fs = state.get("forecast_data") or {}
        case = fs.get("case", "CASE_C")
        req_loc = fs.get("requested_location", location)

        if case == "CASE_C" or not fs.get("forecast_available"):
            lines = [
                "XGBOOST PM2.5 FORECAST & SHAP REPORT (DATA COVERAGE NOTICE)",
                "=" * 78,
                f"Target Location: {req_loc}",
                f"Geocoded Location: {fs.get('resolved_location', req_loc)}",
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

        lines = [
            "XGBOOST PM2.5 FORECAST & SHAP EXPLAINABILITY REPORT",
            "=" * 78,
            f"Target Location: {req_loc}",
            f"Resolved Location: {fs.get('resolved_location', req_loc)}",
            f"Forecast Strategy: {case} — {fs.get('forecast_method_label', 'Direct Forecast')}",
            f"Model Architecture: {fs.get('model_name', 'Multi-Station XGBoost Regressor')}",
            f"Forecast Horizon: Next 1 Hour",
            "",
            "XGBOOST FORECAST PREDICTION",
            "-" * 78,
            f"Predicted Next-Hour PM2.5: {fs.get('predicted_pm25')} {fs.get('unit', 'µg/m³')}",
            f"Baseline Expected Value (E[y]): {fs.get('shap_baseline', 41.0):.2f} {fs.get('unit', 'µg/m³')}",
            f"Classification: {'SPATIALLY ESTIMATED FORECAST' if fs.get('is_spatial_estimate') else 'DIRECT CPCB IN-SITU FORECAST'}",
            "",
            "CONTRIBUTING MONITORING STATIONS",
            "-" * 78,
        ]

        for st in fs.get("contributing_stations", []):
            obs_str = f"{st.get('observed_pm25'):.1f} µg/m³" if st.get('observed_pm25') is not None else "N/A"
            lines.append(
                f"- {st['clean_name']:<20} | Dist: {st['distance_km']:>5.2f} km | Weight: {st.get('weight', 1.0):>5.1%} | Observed: {obs_str}"
            )

        lines.extend([
            "",
            "SHAP ATTRIBUTION BREAKDOWN (TreeExplainer)",
            "-" * 78,
            "Exact additive feature contributions pushing the prediction higher (+) or lower (-):",
            "",
        ])

        for i, f in enumerate(fs.get("shap_contributions", [])[:10], start=1):
            val = f.get("feature_value")
            val_str = f"{val:.2f}" if isinstance(val, (int, float)) else str(val)
            lines.append(
                f"{i:2d}. {f['feature']:<24} | SHAP: {f['shap_value']:>+8.4f} | Observed: {val_str:<8} | {f['effect']}"
            )

        lines.extend([
            "",
            "MODEL INTERPRETABILITY INSIGHT",
            "-" * 78,
            f"- Primary Driving Factor: {fs.get('shap_contributions', [{}])[0].get('feature', 'pm25')}",
            "- Note: SHAP quantifies statistical feature attributions of the model;",
            "  it reflects learned associations rather than physical causal proof.",
        ])
        return {"final_answer": "\n".join(lines)}

    # ---------------------------------------------------------
    # DBSCAN HOTSPOTS
    # ---------------------------------------------------------
    if intent == "dbscan":
        db = state.get("dbscan_data") or {}
        stations = db.get("stations", [])
        matched = None
        if location.lower() != "pune":
            for s in stations:
                if location.lower() in s["station"].lower() or s["station"].lower() in location.lower():
                    matched = s
                    break

        lines = [
            "DBSCAN SPATIAL HOTSPOT & CLUSTERING REPORT",
            "=" * 78,
            f"Target Region: {location if location != 'Pune' else 'Pune Metropolitan Area'}",
            "Clustering Algorithm: DBSCAN (Density-Based Spatial Clustering of Applications with Noise)",
            f"Hyperparameters: {db.get('hyperparameters', 'eps=0.75, min_samples=2')}",
            f"Total Monitored Stations: {len(stations)}",
            f"Identified Hotspot Stations: {db.get('hotspot_count', 0)}",
            "",
        ]

        if matched:
            lines.extend([
                f"SPECIFIC LOCALITY STATUS: {matched['station']}",
                "-" * 78,
                f"Current Mean PM2.5: {matched['pm25']:.1f} µg/m³",
                f"Hotspot Classification: {matched['category'].upper()}",
                f"Coordinates: {matched['latitude']:.4f}, {matched['longitude']:.4f}",
                f"Spatial Cluster: Cluster {matched['cluster']}" if matched['cluster'] != -1 else "Spatial Cluster: Isolated / Boundary Station",
                "",
            ])

        lines.extend([
            "ALL STATIONS & SPATIAL CLUSTERS (RANKED BY PROCESSED-DATASET MEAN PM2.5)",
            "-" * 78,
            "Metric: Processed-dataset mean PM2.5; not confirmed live readings.",
        ])

        for i, s in enumerate(stations, start=1):
            display_name = str(s.get("station", "Unknown")).replace("_", " ").strip()
            cluster_id = int(s.get("cluster", -1))
            spatial_status = f"Cluster {cluster_id}" if cluster_id != -1 else "Isolated"
            category = str(s.get("category", "Unclassified"))
            pollution_status = (
                category if "hotspot" in category.casefold()
                else "Not classified as a pollution hotspot"
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

    # ---------------------------------------------------------
    # RAG / POLICY
    # ---------------------------------------------------------
    if intent == "policy_rag":
        policy = state.get("policy") or "No policy documents found matching your query."
        lines = [
            "CPCB / NAAQS ENVIRONMENTAL POLICY & REGULATION REPORT",
            "=" * 78,
            "",
            str(policy).strip(),
            "",
            "-" * 78,
            "Source: Central Pollution Control Board (CPCB) Regulatory Knowledge Base (RAG)",
        ]
        return {"final_answer": "\n".join(lines)}

    # ---------------------------------------------------------
    # RECOMMENDATIONS
    # ---------------------------------------------------------
    if intent == "recommendation":
        env = state.get("environment") or {}
        curr = env.get("current") or {}
        aqi_obj = env.get("current_aqi") or {}
        recs = state.get("recommendations") or env.get("recommendations") or []

        lines = [
            f"AIR POLLUTION CONTROL & MITIGATION RECOMMENDATIONS — {location}",
            "=" * 78,
            "",
            "CURRENT ENVIRONMENTAL CONTEXT",
            "-" * 78,
            f"• Current AQI     : {aqi_obj.get('value', 'N/A')} ({aqi_obj.get('category', 'N/A')})",
            f"• PM2.5 Level     : {curr.get('pm2_5', 'N/A')} µg/m³",
            f"• Wind Conditions : {curr.get('wind_speed_kph', 'N/A')} km/h ({curr.get('wind_direction', 'N/A')})",
            f"• Ambient Humidity: {curr.get('humidity', 'N/A')} %",
            "",
            "ACTIONABLE MITIGATION PROTOCOLS",
            "-" * 78,
        ]

        if recs:
            for r in recs:
                lines.append(f"• {r}")
        else:
            lines.append("• Maintain routine continuous ambient monitoring.")

        lines.extend([
            "",
            "REGULATORY ADVISORY",
            "-" * 78,
            "Actionable protocols derived in compliance with CPCB Comprehensive Air Action Plan.",
        ])
        return {"final_answer": "\n".join(lines)}

    # ---------------------------------------------------------
    # LIVE AQI & WEATHER (DEFAULT)
    # ---------------------------------------------------------
    env = state.get("environment") or {}

    # Do not present empty or failed live data as a successful live report.
    if env.get("status") in {"error", "degraded"}:
        reason = env.get("error") or "the primary and fallback providers returned no usable data"
        return {
            "final_answer": (
                f"Current AQI/weather data for {location} is unavailable. "
                f"Reason: {reason}. No pollutant values have been invented. "
                "Try again later or check the official CPCB monitoring source."
            )
        }

    curr = env.get("current") or {}
    aqi_obj = env.get("current_aqi") or {}
    pred = env.get("prediction") or {}
    recs = env.get("recommendations") or []
    loc_meta = env.get("location") or {}
    req_loc = loc_meta.get('requested_location', location)
    disp_loc = loc_meta.get('display_name', location)
    api_loc = loc_meta.get('weatherapi_location')

    if api_loc and req_loc.lower() not in [api_loc.lower(), "pune"] and "pune" in api_loc.lower():
        resolved_station_str = f"WeatherAPI Station ({api_loc}) [Fallback station serving {req_loc}]"
    else:
        resolved_station_str = disp_loc

    lines = [
        f"LIVE AIR QUALITY & WEATHER INTELLIGENCE REPORT - {location}",
        "=" * 78,
        f"Target Location : {req_loc}",
        f"Resolved Station: {resolved_station_str}",
        f"Last Observed   : {curr.get('last_updated', 'N/A') or loc_meta.get('local_time', 'N/A')}",
        "",
        "POLLUTANT CONCENTRATIONS",
        "-" * 78,
        f"- Air Quality Index (AQI) : {aqi_obj.get('value', 'N/A')} ({aqi_obj.get('category', 'N/A')})",
        f"- PM2.5 (Fine Particulate): {curr.get('pm2_5', 'N/A')} ug/m3",
        f"- PM10 (Respirable Dust)  : {curr.get('pm10', 'N/A')} ug/m3",
        f"- NO2 (Nitrogen Dioxide)  : {curr.get('no2', 'N/A')} ug/m3",
        f"- SO2 (Sulfur Dioxide)    : {curr.get('so2', 'N/A')} ug/m3",
        f"- CO (Carbon Monoxide)    : {curr.get('co', 'N/A')} ug/m3",
        f"- O3 (Ground Ozone)       : {curr.get('o3', 'N/A')} ug/m3",
        "",
        "METEOROLOGICAL CONDITIONS",
        "-" * 78,
        f"- Temperature : {curr.get('temperature_c', 'N/A')} C (Feels like: {curr.get('feels_like_c', 'N/A')} C)",
        f"- Humidity    : {curr.get('humidity', 'N/A')} %",
        f"- Wind Speed  : {curr.get('wind_speed_kph', 'N/A')} km/h ({curr.get('wind_direction', 'N/A')})",
        f"- Rainfall    : {curr.get('rainfall_mm', 'N/A')} mm",
        f"- Condition   : {curr.get('condition', 'N/A')}",
        "",
        "INDICATIVE TREND & HEALTH ADVISORY",
        "-" * 78,
        f"- Short-term PM2.5 Trend: {pred.get('label', 'Stable')}",
    ]

    if recs:
        lines.append(f"- Health Advisory: {recs[0]}")

    lines.extend([
        "",
        f"Data Provenance: {env.get('data_provenance', {}).get('primary_source', 'WeatherAPI Air Quality Network')}",
    ])

    provenance = env.get("data_provenance") or {}
    if "Open-Meteo" in str(provenance.get("primary_source", "")):
        lines.extend([
            "",
            "DATA QUALITY NOTICE",
            "-" * 78,
            "Fallback values are model-based estimates for the nearest available grid cell, not a Kharadi street-level sensor reading.",
            "The displayed AQI is the provider's US AQI scale, not India's CPCB National AQI. For official Indian AQI, verify CPCB/MPCB station data.",
        ])

    return {"final_answer": "\n".join(lines)}


# ============================================================
# LANGGRAPH BUILDER
# ============================================================


def multi_agent_node(state: dict) -> dict:
    """Run selected specialists sequentially with isolated intermediate state."""
    requested = state.get("requested_intents") or []
    labels = {
        "live_aqi": "Live AQI and weather",
        "forecast": "Forecast and SHAP",
        "dbscan": "DBSCAN hotspots",
        "policy_rag": "Policy and regulations",
        "recommendation": "Mitigation recommendations",
    }
    handlers = {
        "live_aqi": weather_node,
        "forecast": forecast_shap_node,
        "dbscan": dbscan_node,
        "policy_rag": rag_node,
        "recommendation": recommendation_node,
    }

    sections = []
    for capability in requested:
        handler = handlers.get(capability)
        if handler is None:
            continue

        label = labels[capability]
        original_question = str(state.get("question", "") or "")
        specialist_question = original_question

        # If a combined request asks for CPCB standards without naming a
        # pollutant, explicitly ask the policy specialist for PM2.5 NAAQS.
        question_lower = original_question.casefold()
        asks_cpcb_standards = (
            "cpcb" in question_lower
            and any(term in question_lower for term in (
                "standard", "standards", "naaqs", "limit", "limits",
            ))
        )
        names_pollutant = any(term in question_lower for term in (
            "pm2.5", "pm 2.5", "pm10", "pm 10", "nitrogen dioxide",
            "sulfur dioxide", "sulphur dioxide", "ozone", "carbon monoxide",
        ))
        if (
            capability == "policy_rag"
            and asks_cpcb_standards
            and not names_pollutant
        ):
            specialist_question = (
                "What are the CPCB National Ambient Air Quality Standards "
                "(NAAQS) for PM2.5 annual average and 24-hour average?"
            )

        substate = {
            "question": specialist_question,
            "location": state.get("location", "Pune"),
            "session_id": state.get("session_id"),
            "intent": capability,
        }
        try:
            result = handler(dict(substate))
            if isinstance(result, dict):
                substate.update(result)
            answer = str(final_node(substate).get("final_answer", "") or "").strip()
            if not answer:
                answer = "This specialist returned no report."
        except Exception as exc:
            answer = (
                "This specialist could not complete its part of the request. "
                f"Technical detail: {type(exc).__name__}: {exc}"
            )

        sections.append(f"## {label}\n\n{answer}")

    if not sections:
        return {
            "final_answer": (
                "I couldn't identify the requested specialist tasks. "
                "Please specify whether you want live AQI, a forecast, "
                "hotspots, policy information, or recommendations."
            )
        }

    return {
        "final_answer": (
            f"ORIVA MULTI-AGENT ENVIRONMENTAL REPORT - "
            f"{state.get('location', 'Pune')}\n\n"
            + "\n\n---\n\n".join(sections)
        )
    }


builder = StateGraph(PollutionState)

builder.add_node("intent", intent_node)
builder.add_node("multi_agent", multi_agent_node)
builder.add_node("direct", direct_node)
builder.add_node("comparison", comparison_node)
builder.add_node("weather", weather_node)
builder.add_node("forecast_shap", forecast_shap_node)
builder.add_node("dbscan", dbscan_node)
builder.add_node("rag", rag_node)
builder.add_node("recommendation", recommendation_node)
builder.add_node("final", final_node)

builder.add_edge(START, "intent")

builder.add_conditional_edges(
    "intent",
    route_after_intent,
    {
        "multi_agent": "multi_agent",
        "direct": "direct",
        "comparison": "comparison",
        "weather": "weather",
        "forecast_shap": "forecast_shap",
        "dbscan": "dbscan",
        "rag": "rag",
        "recommendation": "recommendation",
    }
)

builder.add_edge("multi_agent", "final")
builder.add_edge("direct", "final")
builder.add_edge("comparison", "final")
builder.add_edge("weather", "final")
builder.add_edge("forecast_shap", "final")
builder.add_edge("dbscan", "final")
builder.add_edge("rag", "final")
builder.add_edge("recommendation", "final")
builder.add_edge("final", END)

app = builder.compile()


# ============================================================
# PUBLIC INTERFACE
# ============================================================

def run_pipeline(state: dict) -> dict:
    """Run pipeline and update conversation session memory."""
    result = app.invoke(state)
    q = state.get("question", "")
    ans = result.get("final_answer", "")
    loc = result.get("location")
    if q and ans:
        SESSION_MEMORY.add_turn(
            q, ans, location=loc, session_id=state.get('session_id')
        )
    return result
