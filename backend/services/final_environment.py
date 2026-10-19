import re

from backend.services.aqi_calculator import (
    calculate_aqi_from_pm25,
    get_aqi_category
)

from backend.services.india_environment import (
    get_environment_for_user
)


def add_aqi_to_environment(result):

    current = result.get(
        "current",
        {}
    )

    pm25 = current.get(
        "pm2_5"
    )

    aqi = calculate_aqi_from_pm25(
        pm25
    )

    current["calculated_aqi"] = aqi

    current["aqi_category"] = (
        get_aqi_category(aqi)
    )

    result["current"] = current

    return result


def get_final_environment(
    question
):

    result = get_environment_for_user(
        question
    )

    return add_aqi_to_environment(
        result
    )


def extract_location(question):

    text = question.strip()

    patterns = [
        r"\baqi\s+(?:of|in|at|for)\s+(.+)",
        r"\bair\s+quality\s+(?:of|in|at|for)\s+(.+)",
        r"\bpollution\s+(?:of|in|at|for)\s+(.+)",
        r"\bwhat\s+is\s+the\s+aqi\s+(?:of|in|at|for)\s+(.+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return match.group(
                1
            ).strip(
                " ?!."
            )

    return text.strip(
        " ?!."
    )


if __name__ == "__main__":

    while True:

        question = input(
            "\nYou: "
        ).strip()

        if question.lower() == "exit":
            break

        try:

            result = get_final_environment(
                question
            )

            location = (
                result.get(
                    "location",
                    {}
                ).get(
                    "requested_location"
                )
            )

            current = result.get(
                "current",
                {}
            )

            print(
                "\nAQI REPORT"
            )

            print(
                "=" * 60
            )

            print(
                "Location:",
                location
            )

            print(
                "PM2.5:",
                current.get("pm2_5"),
                "µg/m³"
            )

            print(
                "PM10:",
                current.get("pm10"),
                "µg/m³"
            )

            print(
                "Calculated AQI:",
                current.get(
                    "calculated_aqi"
                )
            )

            print(
                "AQI Category:",
                current.get(
                    "aqi_category"
                )
            )

        except Exception as exc:

            print(
                "ERROR:",
                exc
            )
