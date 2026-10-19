from __future__ import annotations

from typing import Any, Dict

from backend.innovation.engine import build_innovation_report


def resolve_location_from_state(state: Dict[str, Any]) -> str:
    """Extract location from state dictionary."""
    return str(
        state.get("location")
        or state.get("resolved_location")
        or state.get("city")
        or "Pune"
    )


def innovation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Additive LangGraph node.

    Uses the existing environment report already produced by the main system.
    It does not replace WeatherAPI, XGBoost, RAG, SHAP, DBSCAN or any
    existing agent.
    """

    report = (
        state.get("environment_report")
        or state.get("environment")
        or state.get("report")
    )

    location = resolve_location_from_state(state)

    if not isinstance(report, dict):
        return {
            "innovation": {
                "available": False,
                "message": "Environment report unavailable."
            }
        }

    result = build_innovation_report(
        report,
        location=location,
    )

    return {
        "innovation": result,
    }


def add_innovation_node(builder: Any) -> Any:
    """
    Registers the node without assuming your existing node names.
    The caller controls where the node is connected.
    """
    builder.add_node("innovation_intelligence", innovation_node)
    return builder
