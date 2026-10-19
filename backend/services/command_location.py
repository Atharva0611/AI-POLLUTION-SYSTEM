import re
from pathlib import Path


def extract_command_location(text: str) -> str:
    text = text.strip()

    # Direct location commands
    patterns = [
        r"rainfall status of\s+(.+)$",
        r"rainfall of\s+(.+)$",
        r"weather(?: forecast)? for\s+(.+)$",
        r"weather of\s+(.+)$",
        r"temperature in\s+(.+)$",
        r"temperature of\s+(.+)$",
        r"aqi of\s+(.+)$",
        r"aqi in\s+(.+)$",
        r"air quality of\s+(.+)$",
        r"air quality in\s+(.+)$",
        r"pollution in\s+(.+)$",
        r"pollution of\s+(.+)$",
        r"forecast for\s+(.+)$",
        r"forecast of\s+(.+)$",
        r"environmental report for\s+(.+)$",
        r"complete environmental report for\s+(.+)$",
        r"report for\s+(.+)$",
        r"for\s+(.+)$",
        r"in\s+(.+)$",
        r"of\s+(.+)$",
    ]

    lowered = text.lower()

    for pattern in patterns:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            location = match.group(1).strip(" ?.!,:;")
            if location:
                return location

    # Check whether the whole command is already a known location
    return text.strip(" ?.!,:;")


def normalize_location(location: str) -> str:
    location = location.strip(" ?.!,:;")
    return " ".join(location.split())
