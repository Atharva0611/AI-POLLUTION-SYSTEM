"""
Centralized Input Validation & Classification Service
======================================================
Provides robust preprocessing and classification:
A. Empty Input (empty, spaces only, blank lines)
B. Numeric-only Input (integers, floats, negative numbers)
C. Greetings (hi, hello, hey, namaste, etc.)
D. Farewells and Conversational (bye, thanks, help, what can you do)
E. Conceptual Pollution / Technical Questions (AQI, PM2.5, PM10, DBSCAN, SHAP, etc.)
F. Unsupported / Out-of-domain (capital of France, jokes, stock prices)
"""

import re
from typing import Dict, Any, Optional

GREETINGS = {
    "hi", "hello", "hey", "heya", "howdy", "hii", "hiii",
    "good morning", "good afternoon", "good evening",
    "namaste", "namaskar", "greetings"
}

FAREWELLS = {
    "bye", "goodbye", "see you", "cya", "exit", "quit", "q",
    "have a nice day", "good night"
}

GRATITUDE = {
    "thanks", "thank you", "thankyou", "thx", "many thanks", "appreciate it"
}

HELP_QUERIES = {
    "help", "help me", "what can you do", "what do you do", "capabilities",
    "commands", "features", "how to use"
}

# Out of domain keywords that should immediately receive domain boundaries
OUT_OF_DOMAIN_PATTERNS = [
    r"\b(capital\s+of|president\s+of|prime\s+minister\s+of)\b",
    r"\b(tell\s+me\s+a\s+joke|joke|funny|riddle)\b",
    r"\b(stock\s+price|cryptocurrency|bitcoin|ethereum|shares|trading)\b",
    r"\b(recipe\s+for|cook|movie|song|actor|actress|cricket\s+score|football)\b",
    r"\b(who\s+won|score\s+of|match\s+between)\b",
    r"\b(write\s+a\s+poem|write\s+a\s+story|lyrics)\b",
]


def is_numeric_only(text: str) -> bool:
    """Check if input consists only of numbers (int, float, negative)."""
    cleaned = text.strip()
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", cleaned):
        return True
    return False


def validate_user_input(raw_input: str) -> Dict[str, Any]:
    """
    Validates and preprocesses user text before hitting any model or agent.
    Returns:
      {
        "valid": bool,
        "type": "empty" | "numeric" | "greeting" | "farewell" | "gratitude" | "help" | "unsupported" | "pollution_query",
        "message": Optional[str],
        "cleaned_text": str
      }
    """
    if raw_input is None:
        return {
            "valid": False,
            "type": "empty",
            "message": "Please enter a question.",
            "cleaned_text": ""
        }

    text = str(raw_input).strip()

    # Case A: Empty Input
    if not text:
        return {
            "valid": False,
            "type": "empty",
            "message": "Please enter a question.",
            "cleaned_text": ""
        }

    # Case B: Numeric-only Input
    if is_numeric_only(text):
        return {
            "valid": False,
            "type": "numeric",
            "message": (
                "Please enter a pollution-related question instead of numbers.\n"
                "Examples:\n"
                "• What is the current AQI of Pune?\n"
                "• Forecast PM2.5 in Wagholi.\n"
                "• What are the pollution hotspots in Pune?\n"
                "• What does NAAQS specify for PM2.5?"
            ),
            "cleaned_text": text
        }

    norm = text.lower()
    norm_clean = re.sub(r"[?!.,;:]+", "", norm).strip()

    # Case C: Greetings
    if norm_clean in GREETINGS or any(norm_clean.startswith(g + " ") for g in GREETINGS):
        # If user only said greeting or greeting + simple word
        if len(norm_clean.split()) <= 3 and not any(term in norm_clean for term in ["aqi", "pm25", "pm2.5", "pune", "delhi", "pollution"]):
            return {
                "valid": False,
                "type": "greeting",
                "message": (
                    "Hello! I am your AI Pollution Assistant.\n"
                    "I provide real-time air quality intelligence, CPCB multi-station forecasts, "
                    "spatial hotspot clustering (DBSCAN), SHAP explainability, and regulatory guidance.\n\n"
                    "How can I help you today? Try:\n"
                    "• 'What is the current AQI of Pune?'\n"
                    "• 'Compare the air quality of Pune and Mumbai.'\n"
                    "• 'Forecast next-hour PM2.5 for Wagholi.'\n"
                    "• 'What are the pollution hotspots in Pune?'"
                ),
                "cleaned_text": text
            }

    # Case D1: Farewells
    if norm_clean in FAREWELLS:
        return {
            "valid": False,
            "type": "farewell",
            "message": "Goodbye! Stay safe, wear a mask in high-AQI zones, and breathe clean.",
            "cleaned_text": text
        }

    # Case D2: Gratitude
    if norm_clean in GRATITUDE:
        return {
            "valid": False,
            "type": "gratitude",
            "message": "You're welcome! Feel free to ask anytime about air pollution, forecasts, or environmental regulations.",
            "cleaned_text": text
        }

    # Case D3: Help
    if norm_clean in HELP_QUERIES:
        return {
            "valid": False,
            "type": "help",
            "message": (
                "Here is what I can do for you:\n"
                "1. Live AQI & Pollutant Breakdown: Current PM2.5, PM10, NO2, SO2, CO, O3 across any Indian city/locality.\n"
                "2. Location-Independent Forecasting: Next-hour PM2.5 projection via Multi-Station XGBoost.\n"
                "3. SHAP Explainability: Exact feature attribution breakdown for any model forecast.\n"
                "4. Spatial Hotspots: DBSCAN density-based hotspot clustering for monitored zones.\n"
                "5. CPCB Policies & NAAQS: Official regulatory thresholds, Air Act compliance, and mitigation guidelines.\n"
                "6. Multi-City Comparison: Compare pollution metrics across multiple cities simultaneously (e.g. 'Compare Pune and Mumbai AQI').\n"
                "7. Actionable Recommendations: Specific engineering and mitigation measures based on atmospheric conditions."
            ),
            "cleaned_text": text
        }

    # Case E: Explicit Out-of-Domain questions
    for pat in OUT_OF_DOMAIN_PATTERNS:
        if re.search(pat, norm):
            return {
                "valid": False,
                "type": "unsupported",
                "message": (
                    "I specialize strictly in air pollution monitoring, forecasting, and environmental policy in India.\n"
                    "I cannot assist with unrelated queries such as general trivia, stock prices, or entertainment.\n\n"
                    "Please ask an environmental or pollution-related question, for example:\n"
                    "• 'What is the current AQI of Mumbai?'\n"
                    "• 'What is the NAAQS standard for PM10?'\n"
                    "• 'Explain what PM2.5 is.'\n"
                    "• 'Show pollution hotspots in Pune.'"
                ),
                "cleaned_text": text
            }

    # Valid pollution-domain query
    return {
        "valid": True,
        "type": "pollution_query",
        "message": None,
        "cleaned_text": text
    }
