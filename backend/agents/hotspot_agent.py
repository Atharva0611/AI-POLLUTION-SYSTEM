# pyrefly: ignore [missing-import]
from backend.ml.dbscan.hotspot_detection import (
    get_hotspot_clusters
)


def hotspot_agent(state):

    try:

        input_data = state.get(
            "input_data"
        )

        if input_data is None:

            return {
                "intent": "hotspot",
                "hotspot_success": False,
                "final_answer": (
                    "Spatial data is missing for "
                    "hotspot analysis."
                ),
                "error": "Missing input_data"
            }

        clusters = get_hotspot_clusters(
            input_data
        )

        if clusters is None:

            clusters = []

        return {
            "intent": "hotspot",
            "hotspot_clusters": clusters,
            "hotspot_success": True,
            "final_answer": (
                f"Hotspot analysis completed. "
                f"Detected {len(clusters)} hotspot groups."
            ),
            "error": "",
        }

    except Exception as exc:

        return {
            "intent": "hotspot",
            "hotspot_success": False,
            "final_answer": (
                "Hotspot analysis could not be completed."
            ),
            "error": str(exc),
        }