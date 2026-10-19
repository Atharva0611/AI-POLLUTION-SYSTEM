from backend.services.forecast_integration import (
    get_xgboost_forecast
)

from backend.services.policy_recommendation import (
    policy_and_recommendation
)


def get_forecast_with_policy(location):

    result = get_xgboost_forecast(
        location
    )

    if not result.get("available"):
        return result

    weather = result.get(
        "weatherapi",
        {}
    )

    current = weather.get(
        "current",
        {}
    )

    pm25 = result.get(
        "predicted_pm25_next_1h"
    )

    if pm25 is None:
        pm25 = current.get(
            "pm2_5"
        )

    policy = policy_and_recommendation(
        pm25=pm25 or 0,
        temperature=current.get(
            "temperature_c"
        ) or 0,
        rainfall=current.get(
            "rainfall_mm"
        ) or 0,
        humidity=current.get(
            "humidity"
        ) or 0,
        wind_speed=current.get(
            "wind_speed_ms"
        ) or 0
    )

    result["policy"] = policy["policy"]
    result["recommendations"] = policy[
        "recommendations"
    ]

    return result


if __name__ == "__main__":

    while True:

        location = input(
            "\nEnter location (or exit): "
        ).strip()

        if location.lower() == "exit":
            break

        result = get_forecast_with_policy(
            location
        )

        print("\nFORECAST")
        print("-" * 60)
        print(
            "Predicted PM2.5:",
            result.get(
                "predicted_pm25_next_1h"
            )
        )

        print(
            "Forecast source:",
            result.get(
                "forecast_source"
            )
        )

        print("\nPOLICY")
        print("-" * 60)

        for item in result.get(
            "policy",
            []
        ):
            print("-", item)

        print("\nRECOMMENDATION")
        print("-" * 60)

        for item in result.get(
            "recommendations",
            []
        ):
            print("-", item)
