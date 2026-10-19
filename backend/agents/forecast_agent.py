# pyrefly: ignore [missing-import]
from backend.services.forecast_service import get_canonical_forecast


def forecast_agent(state):
    try:
        input_data = state.get("input_data") or state.get("location") or "Pune"

        res = get_canonical_forecast(str(input_data))

        if not res.get("forecast_available"):
            return {
                "intent": "forecast",
                "forecast_success": False,
                "case": res.get("case", "CASE_C"),
                "final_answer": (
                    f"Forecast unavailable for {input_data}: {res.get('reason', 'Insufficient local CPCB data.')}"
                ),
                "error": res.get("reason", "Forecast suppressed"),
            }

        prediction = res.get("predicted_pm25")
        method_lbl = res.get("forecast_method_label", "Station Forecast")

        return {
            "intent": "forecast",
            "forecast_pm25": float(prediction),
            "forecast_success": True,
            "case": res.get("case"),
            "is_spatial_estimate": res.get("is_spatial_estimate", False),
            "contributing_stations": res.get("contributing_stations", []),
            "final_answer": (
                f"Predicted next-hour PM2.5 for {res.get('resolved_location')}: "
                f"{float(prediction):.2f} µg/m³ ({method_lbl})"
            ),
            "error": "",
        }

    except Exception as exc:

        return {
            "intent": "forecast",
            "forecast_success": False,
            "final_answer": (
                "Forecast could not be generated."
            ),
            "error": str(exc),
        }