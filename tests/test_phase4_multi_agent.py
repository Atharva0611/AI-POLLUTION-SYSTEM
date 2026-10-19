import backend.agents.orchestrator as orchestrator


def test_combined_request_detects_multiple_specialists():
    question = (
        "Show current AQI in Pune, forecast PM2.5, "
        "identify hotspots, and explain CPCB policy"
    )
    requested = orchestrator.detect_multi_agent_intents(question, "live_aqi")

    assert "live_aqi" in requested
    assert "forecast" in requested
    assert "dbscan" in requested
    assert "policy_rag" in requested


def test_single_aqi_request_keeps_existing_route():
    requested = orchestrator.detect_multi_agent_intents(
        "What is the current AQI in Pune?", "live_aqi"
    )
    assert requested == []
    assert orchestrator.route_after_intent({
        "intent": "live_aqi",
        "requested_intents": requested,
    }) == "weather"


def test_multi_agent_runs_specialists_and_combines_one_answer(monkeypatch):
    calls = []

    def fake_weather(state):
        calls.append(("weather", state))
        return {"environment": {"status": "ok"}}

    def fake_forecast(state):
        calls.append(("forecast", state))
        return {"forecast_data": {"forecast_available": True}}

    def fake_dbscan(state):
        calls.append(("dbscan", state))
        return {"dbscan_data": {"stations": []}}

    def fake_rag(state):
        calls.append(("rag", state))
        return {"policy": "Policy test result"}

    def fake_final(state):
        return {"final_answer": f"Result for {state['intent']}"}

    monkeypatch.setattr(orchestrator, "weather_node", fake_weather)
    monkeypatch.setattr(orchestrator, "forecast_shap_node", fake_forecast)
    monkeypatch.setattr(orchestrator, "dbscan_node", fake_dbscan)
    monkeypatch.setattr(orchestrator, "rag_node", fake_rag)
    monkeypatch.setattr(orchestrator, "final_node", fake_final)

    result = orchestrator.multi_agent_node({
        "question": "AQI, forecast, hotspots, policy",
        "location": "Pune",
        "session_id": "multi-agent-test",
        "requested_intents": [
            "live_aqi", "forecast", "dbscan", "policy_rag"
        ],
    })

    assert [name for name, _ in calls] == [
        "weather", "forecast", "dbscan", "rag"
    ]
    answer = result["final_answer"]
    assert "Live AQI and weather" in answer
    assert "Forecast and SHAP" in answer
    assert "DBSCAN hotspots" in answer
    assert "Policy and regulations" in answer
    assert answer.count("Result for") == 4


def test_specialist_state_is_isolated(monkeypatch):
    seen_states = []

    def fake_weather(state):
        state["environment"] = {"from": "weather"}
        seen_states.append(state)
        return {"environment": {"from": "weather"}}

    def fake_rag(state):
        seen_states.append(state)
        assert "environment" not in state
        return {"policy": "Policy result"}

    monkeypatch.setattr(orchestrator, "weather_node", fake_weather)
    monkeypatch.setattr(orchestrator, "rag_node", fake_rag)
    monkeypatch.setattr(
        orchestrator,
        "final_node",
        lambda state: {"final_answer": f"OK {state['intent']}"},
    )

    orchestrator.multi_agent_node({
        "question": "AQI and policy",
        "location": "Pune",
        "requested_intents": ["live_aqi", "policy_rag"],
    })

    assert len(seen_states) == 2
    assert seen_states[0] is not seen_states[1]


def test_one_specialist_failure_does_not_hide_other_results(monkeypatch):
    def failing_weather(state):
        raise RuntimeError("simulated weather outage")

    def fake_rag(state):
        return {"policy": "Policy result available"}

    monkeypatch.setattr(orchestrator, "weather_node", failing_weather)
    monkeypatch.setattr(orchestrator, "rag_node", fake_rag)
    monkeypatch.setattr(
        orchestrator,
        "final_node",
        lambda state: {"final_answer": "Policy specialist succeeded"},
    )

    result = orchestrator.multi_agent_node({
        "question": "AQI and policy",
        "location": "Pune",
        "requested_intents": ["live_aqi", "policy_rag"],
    })

    answer = result["final_answer"]
    assert "could not complete" in answer
    assert "simulated weather outage" in answer
    assert "Policy specialist succeeded" in answer


def test_compiled_graph_routes_combined_question_to_coordinator(monkeypatch):
    calls = []

    def fake_weather(state):
        calls.append("live_aqi")
        return {
            "environment": {
                "status": "error",
                "error": "simulated offline service",
            }
        }

    def fake_rag(state):
        calls.append("policy_rag")
        return {
            "policy": "Mock CPCB policy answer.",
            "policy_success": True,
        }

    monkeypatch.setattr(orchestrator, "weather_node", fake_weather)
    monkeypatch.setattr(orchestrator, "rag_node", fake_rag)

    result = orchestrator.app.invoke({
        "question": "Show current AQI in Pune and explain CPCB policy",
        "location": "Pune",
        "session_id": "compiled-graph-multi-agent-test",
    })

    assert "live_aqi" in calls
    assert "policy_rag" in calls
    assert "Live AQI and weather" in result["final_answer"]
    assert "Policy and regulations" in result["final_answer"]
    assert "unavailable" in result["final_answer"].lower()
    assert "Mock CPCB policy answer." in result["final_answer"]


def test_combined_report_detects_live_air_quality_hotspots_and_policy():
    question = (
        "Give me a combined report for Pune covering air quality, "
        "hotspots, and CPCB standards."
    )
    requested = orchestrator.detect_multi_agent_intents(question, "policy_rag")

    assert "live_aqi" in requested
    assert "dbscan" in requested
    assert "policy_rag" in requested


def test_combined_cpcb_standards_request_targets_pm25_naaqs(monkeypatch):
    captured = []

    def fake_rag(state):
        captured.append(state["question"])
        return {"policy": "Mock targeted standards answer."}

    def fake_final(state):
        return {"final_answer": state.get("policy", "Mock answer.")}

    monkeypatch.setattr(orchestrator, "rag_node", fake_rag)
    monkeypatch.setattr(orchestrator, "final_node", fake_final)

    result = orchestrator.multi_agent_node({
        "question": (
            "Give me a combined report for Pune covering air quality, "
            "hotspots, and CPCB standards."
        ),
        "location": "Pune",
        "session_id": "targeted-cpcb-standards-test",
        "requested_intents": ["live_aqi", "dbscan", "policy_rag"],
    })

    assert len(captured) == 1
    assert "PM2.5" in captured[0]
    assert "annual average" in captured[0]
    assert "24-hour average" in captured[0]
    assert "Mock targeted standards answer." in result["final_answer"]
