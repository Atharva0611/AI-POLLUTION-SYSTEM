import re
import requests

NOMINATIM_URL = (
    "https://nominatim.openstreetmap.org/search"
)

HEADERS = {
    "User-Agent": "AI-Pollution-System/1.0"
}


def extract_location(question: str):

    text = question.strip()

    text = re.sub(
        r"[?.!]+$",
        "",
        text
    ).strip()

    patterns = [

        r"(?:what\s+is\s+)?(?:the\s+)?rainfall"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        r"(?:what\s+is\s+)?(?:the\s+)?rain"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        r"(?:what\s+is\s+)?(?:the\s+)?temperature"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        r"(?:what\s+is\s+)?(?:the\s+)?weather"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        r"(?:what\s+is\s+)?(?:the\s+)?aqi"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        r"(?:what\s+is\s+)?(?:the\s+)?air\s+quality"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        r"(?:what\s+is\s+)?(?:the\s+)?pollution"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        r"(?:what\s+is\s+)?(?:the\s+)?pm\s*2\.?5"
        r"(?:\s+status|\s+situation|\s+forecast)?"
        r"\s+(?:of|in|at|for)\s+(.+)",

        r"(?:what\s+is\s+)?(?:the\s+)?forecast"
        r"\s+(?:of|in|at|for)\s+(.+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            location = match.group(
                1
            ).strip()

            if location:
                return location

    return text


def resolve_location(location):

    # First try the extracted location directly.
    queries = [
        f"{location}, Pune, Maharashtra, India",
        f"{location}, Maharashtra, India",
        f"{location}, India"
    ]

    for query in queries:

        try:

            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "in",
                    "addressdetails": 1
                },
                headers=HEADERS,
                timeout=20
            )

            response.raise_for_status()

            results = response.json()

            if results:

                item = results[0]

                return {
                    "requested_location": location,
                    "resolved_name": item.get(
                        "name",
                        location
                    ),
                    "display_name": item.get(
                        "display_name",
                        location
                    ),
                    "latitude": float(
                        item["lat"]
                    ),
                    "longitude": float(
                        item["lon"]
                    )
                }

        except Exception:
            continue

    raise ValueError(
        f"Location not found: {location}"
    )


def resolve_user_question(question):

    location = extract_location(
        question
    )

    if not location:
        raise ValueError(
            "Could not extract a location from the question."
        )

    return resolve_location(
        location
    )


if __name__ == "__main__":

    tests = [
        "What is the rainfall status of Wagholi?",
        "Aqi of Alandi",
        "What is the temperature in Kharadi?",
        "What is the weather forecast for Wakad?",
        "What is the air quality of Bhosari?"
    ]

    for question in tests:

        try:

            result = resolve_user_question(
                question
            )

            print(
                f"{question} -> "
                f"{result['requested_location']}"
            )

        except Exception as exc:

            print(
                f"{question} -> ERROR: {exc}"
            )
