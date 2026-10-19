
from pathlib import Path
import os
import re
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

API_KEY = os.getenv("WEATHER_API_KEY")

SEARCH_URL = (
    "https://api.weatherapi.com/v1/search.json"
)


def normalize(text):
    text = str(text or "").strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"[?!.,;:]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_candidate(text):
    text = str(text or "").strip()
    text = re.sub(r"[?!.,;:]+$", "", text)
    text = re.sub(
        r"\b(right now|currently|today|tonight|now)\b.*$",
        "",
        text,
        flags=re.IGNORECASE
    )
    return text.strip()


def extract_location_phrase(question):

    q = normalize(question)

    if not q:
        return None

    patterns = [

        r"(?:weather\s+condition|weather\s+conditions)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:current\s+weather)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:weather)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:rainfall|rain|raining)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:temperature)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:humidity)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:wind\s+speed|wind\s+direction)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:aqi)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:air\s+quality)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:pollution)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:forecast)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:environmental\s+report)"
        r"\s+(?:in|of|for|at)\s+(.+)$",

        r"(?:environmental\s+conditions?)"
        r"\s+(?:in|of|for|at)\s+(.+)$",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            q
        )

        if match:

            candidate = clean_candidate(
                match.group(1)
            )

            if candidate:
                return candidate

    # Generic fallback:
    # "what is happening in Beed"
    for pattern in [
        r"\bin\s+(.+)$",
        r"\bof\s+(.+)$",
        r"\bfor\s+(.+)$",
        r"\bat\s+(.+)$",
    ]:

        match = re.search(
            pattern,
            q
        )

        if match:

            candidate = clean_candidate(
                match.group(1)
            )

            if candidate:
                return candidate

    return None


def search_india_location(location_text):

    if not API_KEY:
        raise RuntimeError(
            "WEATHER_API_KEY is missing in .env"
        )

    candidate = clean_candidate(
        location_text
    )

    if not candidate:
        return None

    try:

        response = requests.get(
            SEARCH_URL,
            params={
                "key": API_KEY,
                "q": candidate,
            },
            timeout=15
        )

        response.raise_for_status()

        results = response.json()

        if not isinstance(
            results,
            list
        ) or not results:

            return None

        # Prefer an Indian match.
        for item in results:

            country_code = str(
                item.get(
                    "country_code",
                    ""
                )
            ).lower()

            country = str(
                item.get(
                    "country",
                    ""
                )
            ).lower()

            if (
                country_code == "in"
                or country == "india"
            ):

                name = item.get(
                    "name"
                )

                region = item.get(
                    "region"
                )

                if name and region:
                    return (
                        f"{name}, {region}, India"
                    )

                if name:
                    return (
                        f"{name}, India"
                    )

        # Search may occasionally omit country_code.
        # In that case use the best WeatherAPI result.
        item = results[0]

        name = item.get(
            "name"
        )

        region = item.get(
            "region"
        )

        if name and region:
            return (
                f"{name}, {region}, India"
            )

        if name:
            return (
                f"{name}, India"
            )

    except Exception:
        pass

    # Important fallback:
    # Let the WeatherAPI Current/Forecast endpoint resolve it.
    # This supports cities/towns not present in our local list.
    return f"{candidate.title()}, India"


def resolve_location(question):

    raw = str(
        question or ""
    ).strip()

    if not raw:
        return None

    aliases = {
        "delhi ncr": "Delhi, India",
        "ncr": "Delhi, India",
        "new delhi": "New Delhi, India",
        "bangalore": "Bengaluru, India",
        "bengaluru": "Bengaluru, India",
        "bombay": "Mumbai, Maharashtra, India",
        "calcutta": "Kolkata, West Bengal, India",
    }

    normalized = normalize(
        raw
    )

    # Direct aliases
    if normalized in aliases:
        return aliases[normalized]

    candidate = extract_location_phrase(
        raw
    )

    if not candidate:

        # The caller may already be giving only a city.
        candidate = raw

    normalized_candidate = normalize(
        candidate
    )

    if normalized_candidate in aliases:
        return aliases[
            normalized_candidate
        ]

    return search_india_location(
        candidate
    )


def require_location(question):

    location = resolve_location(
        question
    )

    if not location:
        raise ValueError(
            "Indian city/location could not be identified from: "
            + str(question)
        )

    return location
