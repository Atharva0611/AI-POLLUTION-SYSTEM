"""
Comprehensive Automated Test Suite for AI Pollution Chatbot System
==================================================================
Covers:
1. Input Validation (empty, numeric, greetings, farewells, unsupported)
2. Intent Routing & Disambiguation (conceptual vs execution: DBSCAN, SHAP, Forecast, AQI, RAG)
3. Location Extraction (Pune, Wagholi, Pune, Nagpur, Pune & Mumbai, conceptual exclusion)
4. Multi-City Comparison & Ranking (mocked data, one city missing)
5. Output Resilience on API/Service Failures (graceful isolation, no raw crashes)
6. Conversation Session Memory (tracking turns, last location, anaphora 'compare both')
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.services.input_validator import validate_user_input, is_numeric_only
from backend.services.conceptual_knowledge import get_conceptual_explanation
from backend.services.location_extractor import (
    extract_single_location,
    extract_comparison_locations,
    extract_locations_from_text,
)
from backend.services.intent_router import classify_intent, extract_location
from backend.services.comparison_service import compare_air_quality
from backend.services.conversation_memory import ConversationMemory
from backend.agents.orchestrator import run_pipeline


# ============================================================
# 1. INPUT VALIDATION TESTS
# ============================================================

def test_input_validation_empty():
    for raw in ["", "   ", "\n\n  \n", None]:
        res = validate_user_input(raw)
        assert res["valid"] is False
        assert res["type"] == "empty"
        assert "Please enter a question" in res["message"]


def test_input_validation_numeric():
    numeric_cases = ["1", "7", "12345", "3.14", "-5", " -42.0 "]
    for raw in numeric_cases:
        assert is_numeric_only(raw) is True
        res = validate_user_input(raw)
        assert res["valid"] is False
        assert res["type"] == "numeric"
        assert "Please enter a pollution-related question" in res["message"]


def test_input_validation_greetings():
    greetings = ["hi", "hello", "hey", "good morning", "good evening", "namaste"]
    for raw in greetings:
        res = validate_user_input(raw)
        assert res["valid"] is False
        assert res["type"] == "greeting"
        assert "Hello! I am your AI Pollution Assistant" in res["message"]


def test_input_validation_farewells_and_gratitude():
    farewells = ["bye", "goodbye", "thanks", "thank you", "help", "what can you do"]
    for raw in farewells:
        res = validate_user_input(raw)
        assert res["valid"] is False
        assert res["type"] in {"farewell", "gratitude", "help"}
        assert res["message"] is not None


def test_input_validation_unsupported_out_of_domain():
    out_of_domain = [
        "What is the capital of France?",
        "Tell me a joke.",
        "What is the stock price?",
        "Who is the prime minister of the UK?",
        "Can you write a poem about flowers?",
    ]
    for raw in out_of_domain:
        res = validate_user_input(raw)
        assert res["valid"] is False
        assert res["type"] == "unsupported"
        assert "I specialize strictly in air pollution monitoring" in res["message"]


# ============================================================
# 2. INTENT ROUTING & CONCEPTUAL DISAMBIGUATION
# ============================================================

def test_intent_routing_conceptual_definitions():
    # What is DBSCAN? -> Must be conceptual, NOT live AQI or DBSCAN clustering run
    concept_dbscan = get_conceptual_explanation("What is DBSCAN?")
    assert concept_dbscan is not None
    assert "Density-Based Spatial Clustering" in concept_dbscan
    assert classify_intent("What is DBSCAN?") == "pollutant_information"

    # What is SHAP? -> Conceptual
    concept_shap = get_conceptual_explanation("What is SHAP?")
    assert concept_shap is not None
    assert "shapley additive explanations" in concept_shap.lower()
    assert classify_intent("What is SHAP?") == "pollutant_information"

    # Explain PM2.5 -> Conceptual
    concept_pm25 = get_conceptual_explanation("Explain PM2.5")
    assert concept_pm25 is not None
    assert "Particulate Matter 2.5" in concept_pm25
    assert classify_intent("Explain PM2.5") == "pollutant_information"

    # What is AQI? -> Conceptual
    concept_aqi = get_conceptual_explanation("What is AQI?")
    assert concept_aqi is not None
    assert "Air Quality Index" in concept_aqi


def test_intent_routing_execution_queries():
    # DBSCAN execution
    assert classify_intent("What are the pollution hotspots in Pune?") == "dbscan"
    assert classify_intent("Run DBSCAN spatial clustering for Pune") == "dbscan"

    # SHAP execution
    assert classify_intent("Explain model prediction using SHAP for Pune") == "shap"
    assert classify_intent("Show feature importance and SHAP values for the forecast") == "shap"

    # Forecasting
    assert classify_intent("Forecast next hour PM2.5 for Wagholi") == "forecast"
    assert classify_intent("Predict tomorrow's air quality in Pune") == "forecast"

    # Live AQI
    assert classify_intent("What is the current AQI of Pune?") == "live_aqi"
    assert classify_intent("Current pollution in Nagpur") == "live_aqi"

    # Comparison
    assert classify_intent("Compare Pune and Mumbai AQI") == "comparison"
    assert classify_intent("Which city has higher pollution, Pune or Nagpur?") == "comparison"

    # Policy RAG
    assert classify_intent("What does NAAQS say about PM10?") == "policy_rag"
    assert classify_intent("Explain CPCB regulations under the Air Act") == "policy_rag"

    # Recommendations
    assert classify_intent("What action can be taken to reduce pollution?") == "recommendation"
    assert classify_intent("Suggestions to mitigate air pollution") == "recommendation"

    # Source Analysis
    assert classify_intent("What are the sources of pollution in Pune?") == "source_analysis"
    assert classify_intent("What causes vehicular emission vs dust?") == "source_analysis"

    # Unsupported unknown query
    assert classify_intent("How do I bake bread in an oven?") == "unsupported"


# ============================================================
# 3. LOCATION EXTRACTION TESTS
# ============================================================

def test_location_extraction_single():
    # "What is the current AQI of Pune?" -> Pune
    assert extract_single_location("What is the current AQI of Pune?") == "Pune"

    # "Give me the latest air quality report for Wagholi, Pune." -> Wagholi, Pune
    assert extract_single_location("Give me the latest air quality report for Wagholi, Pune.") == "Wagholi, Pune"

    # "Current pollution in Nagpur." -> Nagpur
    assert extract_single_location("Current pollution in Nagpur.") == "Nagpur"

    # "Air quality in Mumbai" -> Mumbai
    assert extract_single_location("Air quality in Mumbai") == "Mumbai"

    # "Pollution report for Delhi" -> Delhi
    assert extract_single_location("Pollution report for Delhi") == "Delhi"


def test_location_extraction_multiple_comparison():
    # "Compare the current AQI of Pune and Mumbai." -> ["Pune", "Mumbai"]
    locs = extract_comparison_locations("Compare the current AQI of Pune and Mumbai.")
    assert "Pune" in locs and "Mumbai" in locs
    assert len(locs) == 2

    # Three cities: "Compare PM2.5 in Delhi, Mumbai, and Pune."
    locs_three = extract_comparison_locations("Compare PM2.5 in Delhi, Mumbai, and Pune.")
    assert set(locs_three) == {"Delhi", "Mumbai", "Pune"}


def test_location_extraction_no_false_positives_in_conceptual():
    # "What is DBSCAN?" -> No location
    assert extract_locations_from_text("What is DBSCAN?") == []
    assert extract_single_location("What is DBSCAN?") is None

    # "Hello" -> No location
    assert extract_locations_from_text("Hello") == []
    assert extract_single_location("Hello") is None

    # "What is the capital of France?" -> No location
    assert extract_locations_from_text("What is the capital of France?") == []


# ============================================================
# 4. MULTI-CITY COMPARISON FLOW TESTS
# ============================================================

@patch("backend.services.comparison_service.get_environment_for_user")
def test_comparison_service_two_valid_cities(mock_get_env):
    def fake_env(city):
        if city.lower() == "pune":
            return {
                "status": "ok",
                "current": {"pm2_5": 25.0, "pm10": 45.0, "temperature_c": 24.0, "last_updated": "2026-09-27 22:00"},
                "current_aqi": {"value": 45, "category": "Good"},
                "data_provenance": {"primary_source": "WeatherAPI"},
            }
        else:
            return {
                "status": "ok",
                "current": {"pm2_5": 85.0, "pm10": 130.0, "temperature_c": 28.0, "last_updated": "2026-09-27 22:00"},
                "current_aqi": {"value": 160, "category": "Moderate"},
                "data_provenance": {"primary_source": "WeatherAPI"},
            }

    mock_get_env.side_effect = fake_env

    report = compare_air_quality(["Pune", "Mumbai"])
    assert "AIR QUALITY COMPARISON REPORT" in report
    assert "Pune" in report
    assert "Mumbai" in report
    assert "Cleaner Air: Pune" in report
    assert "Higher Pollution: Mumbai" in report
    assert "AQI Disparity" in report


@patch("backend.services.comparison_service.get_environment_for_user")
def test_comparison_service_one_missing_city(mock_get_env):
    def fake_env(city):
        if city.lower() == "pune":
            return {
                "status": "ok",
                "current": {"pm2_5": 25.0, "pm10": 45.0, "temperature_c": 24.0},
                "current_aqi": {"value": 45, "category": "Good"},
            }
        else:
            raise RuntimeError("Station connection timed out")

    mock_get_env.side_effect = fake_env

    report = compare_air_quality(["Pune", "AtlantisCity"])
    assert "AIR QUALITY COMPARISON REPORT" in report
    assert "Pune" in report
    assert "atlantiscity" in report.lower()
    assert "Data is available only for Pune" in report


# ============================================================
# 5. OUTPUT RESILIENCE ON API / SERVICE FAILURES
# ============================================================

@patch("backend.agents.orchestrator.get_environment_for_user")
def test_pipeline_resilience_on_weather_api_failure(mock_get_env):
    mock_get_env.side_effect = Exception("WeatherAPI down for maintenance")

    state = {
        "question": "What is the current AQI of Pune?",
        "session_id": "test_session",
    }
    result = run_pipeline(state)
    assert result is not None
    assert "final_answer" in result
    answer = result["final_answer"]
    # The pipeline should fail gracefully without implying live readings exist.
    assert "unavailable" in answer.lower()
    assert "no current pollutant readings" in answer.lower()
    assert "LIVE AIR QUALITY & WEATHER INTELLIGENCE REPORT" not in answer
    assert "Pune" in answer
    mock_get_env.assert_called_once()


# ============================================================
# 6. CONVERSATION SESSION MEMORY TESTS
# ============================================================

def test_conversation_memory_tracking():
    mem = ConversationMemory()
    assert mem.get_last_location() is None
    assert mem.get_recent_locations() == []

    # Turn 1
    mem.add_turn("What is the current AQI of Pune?", "Here is Pune AQI...", location="Pune")
    assert mem.get_last_location() == "Pune"
    assert mem.get_recent_locations() == ["Pune"]

    # Turn 2
    mem.add_turn("What about Mumbai?", "Here is Mumbai AQI...", location="Mumbai")
    assert mem.get_last_location() == "Mumbai"
    assert mem.get_recent_locations() == ["Pune", "Mumbai"]

    # Anaphora: "Compare both"
    comp_locs = extract_comparison_locations("Compare both", memory_locations=mem.get_recent_locations())
    assert comp_locs == ["Pune", "Mumbai"]
