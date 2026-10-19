from backend.agents.state import PollutionState


def validation_agent(state: PollutionState) -> PollutionState:
    """
    Validate the outputs produced by the other agents.
    """

    errors = []

    # --------------------------------------------------
    # Forecast validation
    # --------------------------------------------------

    forecast = state.get("forecast_pm25")

    if forecast is not None:

        if not isinstance(
            forecast,
            (int, float)
        ):
            errors.append(
                "Forecast value is not numeric."
            )

        elif forecast < 0:
            errors.append(
                "Forecast PM2.5 cannot be negative."
            )

    # --------------------------------------------------
    # Anomaly validation
    # --------------------------------------------------

    anomaly = state.get(
        "anomaly_detected"
    )

    if anomaly is not None:

        if not isinstance(
            anomaly,
            bool
        ):
            errors.append(
                "Anomaly result must be boolean."
            )

    # --------------------------------------------------
    # Hotspot validation
    # --------------------------------------------------

    hotspots = state.get(
        "hotspot_clusters"
    )

    if hotspots is not None:

        if not isinstance(
            hotspots,
            list
        ):
            errors.append(
                "Hotspot result must be a list."
            )

    # --------------------------------------------------
    # Policy/RAG validation
    # --------------------------------------------------

    policy = state.get(
        "policy_answer"
    )

    if policy is not None:

        if not isinstance(
            policy,
            str
        ):
            errors.append(
                "Policy answer must be text."
            )

        elif len(policy.strip()) == 0:
            errors.append(
                "Policy answer is empty."
            )

    # --------------------------------------------------
    # Final validation
    # --------------------------------------------------

    if errors:

        return {
            **state,
            "error": "; ".join(errors),
            "final_answer": None
        }

    # --------------------------------------------------
    # Build final answer
    # --------------------------------------------------

    answer_parts = []

    if forecast is not None:

        answer_parts.append(
            f"Next-hour PM2.5 forecast: "
            f"{forecast:.2f} µg/m³."
        )

    if anomaly is not None:

        if anomaly:
            answer_parts.append(
                "An unusual pollution event "
                "was detected."
            )
        else:
            answer_parts.append(
                "No unusual pollution event "
                "was detected."
            )

    if hotspots:

        answer_parts.append(
            f"{len(hotspots)} pollution hotspot "
            f"cluster(s) were identified."
        )

    if policy:

        answer_parts.append(
            f"\nPolicy information:\n{policy}"
        )

    final_answer = "\n".join(
        answer_parts
    )

    if not final_answer:

        final_answer = (
            "The system completed validation, "
            "but no result was produced."
        )

    return {
        **state,
        "final_answer": final_answer,
        "error": None
    }


if __name__ == "__main__":
    print(
        "Validation Agent loaded successfully."
    )