# pyrefly: ignore [missing-import]
from backend.ml.anomaly_detection.predict_anomaly import (
    detect_single
)


def anomaly_agent(state):

    try:

        input_data = state.get(
            "input_data"
        )

        if input_data is None:

            return {
                "intent": "anomaly",
                "anomaly_success": False,
                "final_answer": (
                    "Anomaly-analysis input is missing."
                ),
                "error": "Missing input_data"
            }

        result = detect_single(
            input_data
        )

        detected = bool(
            result.get(
                "anomaly_detected",
                False
            )
        )

        score = result.get(
            "anomaly_score"
        )

        if detected:

            message = (
                "An anomaly was detected in "
                "the pollution observation."
            )

        else:

            message = (
                "No significant anomaly was "
                "detected in the observation."
            )

        return {
            "intent": "anomaly",
            "anomaly_detected": detected,
            "anomaly_score": score,
            "anomaly_success": True,
            "final_answer": message,
            "error": "",
        }

    except Exception as exc:

        return {
            "intent": "anomaly",
            "anomaly_success": False,
            "final_answer": (
                "Anomaly analysis could not be completed."
            ),
            "error": str(exc),
        }