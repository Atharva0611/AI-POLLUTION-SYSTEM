import pytest

from backend.agents.orchestrator import route_after_intent


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        ("comparison", "comparison"),
        ("live_aqi", "weather"),
        ("weather", "weather"),
        ("forecast", "forecast_shap"),
        ("shap", "forecast_shap"),
        ("dbscan", "dbscan"),
        ("policy_rag", "rag"),
        ("cpcb", "rag"),
        ("historical_data", "rag"),
        ("recommendation", "recommendation"),
        ("pollutant_information", "direct"),
        ("source_analysis", "rag"),
        ("unsupported", "direct"),
        ("clarification_required", "direct"),
    ],
)
def test_phase4_known_intents_route_to_expected_node(intent, expected):
    assert route_after_intent({"intent": intent}) == expected


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"intent": None},
        {"intent": "unexpected_unknown_intent"},
    ],
)
def test_phase4_unknown_intents_use_safe_direct_route(state):
    assert route_after_intent(state) == "direct"

