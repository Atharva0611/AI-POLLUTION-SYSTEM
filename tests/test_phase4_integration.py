from unittest.mock import patch

from backend.agents.orchestrator import run_pipeline


def test_phase4_unsupported_question_returns_direct_message():
    result = run_pipeline({"question": "How do I bake bread in an oven?"})

    assert isinstance(result, dict)
    assert result.get("intent") == "unsupported"
    assert "direct_message" in result
    assert "specialize" in result["direct_message"].lower()


def test_phase4_missing_question_returns_direct_message():
    result = run_pipeline({"question": ""})

    assert isinstance(result, dict)
    assert result.get("intent") == "empty"
    assert result.get("direct_message") == "Please enter a question."


def test_phase4_forecast_service_failure_is_handled():
    with patch(
        "backend.agents.orchestrator.get_canonical_forecast",
        side_effect=RuntimeError("simulated forecast outage"),
    ):
        result = run_pipeline({
            "question": "Forecast next hour PM2.5 for Pune",
            "location": "Pune",
        })

    assert isinstance(result, dict)
    assert result.get("intent") == "forecast"
    forecast = result.get("forecast_data")
    assert isinstance(forecast, dict)
    assert forecast.get("forecast_available") is False


def test_phase4_policy_question_returns_pipeline_state():
    # Verify the compiled workflow's returned state contract.
    # This is not a simulated RAG-outage test.
    result = run_pipeline({
        "question": "What does NAAQS say about PM10?",
        "location": "Pune",
    })

    assert isinstance(result, dict)
    assert result.get("intent") == "policy_rag"
