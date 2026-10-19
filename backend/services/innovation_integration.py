from __future__ import annotations

from typing import Any, Dict

from backend.innovation.engine import build_innovation_report


def enrich_environment_report(environment_report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add the optional Pollution Decision Intelligence layer.

    Existing environment-report data is preserved unchanged.
    The innovation result is added under the `innovation` key.
    """
    result = dict(environment_report)

    try:
        innovation = build_innovation_report(environment_report)
        result["innovation"] = innovation
        result["innovation_status"] = "available"
    except Exception as exc:
        # Innovation is additive and must never break the existing system.
        result["innovation"] = {}
        result["innovation_status"] = "unavailable"
        result["innovation_error"] = str(exc)

    return result
