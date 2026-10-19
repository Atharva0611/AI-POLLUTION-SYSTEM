from backend.agents.final_agent import app


def usage():

    print("""
============================================================
AI POLLUTION ENVIRONMENTAL INTELLIGENCE SYSTEM
============================================================

Ask any question normally.

Examples:
  Beed
  What is the weather condition in Beed?
  What is the AQI of Delhi?
  What is rainfall in Nashik?
  How can vehicle pollution be controlled?
  What are the National Ambient Air Quality Standards?
  Give me the complete environmental report for Alandi.

Type "exit" to close.

============================================================
""")


def main():

    usage()
    # PHASE4_SESSION_FOLLOWUP: retain context during this terminal session.
    previous_question = ""
    previous_location = "Pune"

    while True:
        try:
            question = input("\nQuestion: ").strip()

            if not question:
                continue

            if question.lower() in {"exit", "quit", "q", "bye"}:
                print("\nSystem stopped.")
                break

            print("\nAnalyzing your question...")

            normalized = question.lower().strip().rstrip("?.! ")
            followup_phrases = {
                "what about tomorrow",
                "and tomorrow",
                "tomorrow",
                "what about today",
                "what about there",
                "what about that",
                "what about it",
                "explain that",
                "what does that mean",
                "why is that",
                "tell me more about that",
            }
            is_followup = bool(previous_question) and normalized in followup_phrases

            effective_question = question

            if is_followup:
                previous_lower = previous_question.lower()
                if (
                    "tomorrow" in normalized
                    and any(word in previous_lower for word in (
                        "forecast", "predict", "prediction", "next hour",
                    ))
                ):
                    effective_question = (
                        f"Forecast PM2.5 for {previous_location} tomorrow. "
                        f"Previous request: {previous_question}. "
                        "Use the existing forecast specialist and report unavailable "
                        "if sufficiently fresh monitoring data is not available."
                    )
                else:
                    effective_question = (
                        f"Previous user request: {previous_question}\n"
                        f"Follow-up question: {question}\n"
                        f"Use the previous task and location ({previous_location}) "
                        "as context. Answer the follow-up directly and do not invent data."
                    )
                print("Using previous question and location as context...")

            result = app.invoke({"question": effective_question})

            answer = result.get("final_answer", "No response generated.")
            print("\n")
            print(answer)

            # Preserve the original user wording for the next follow-up.
            if not is_followup:
                previous_question = question
                import re
                match = re.search(
                    r"\b(?:in|for|at|near)\s+([A-Z][a-zA-Z-]+(?:\s+[A-Z][a-zA-Z-]+){0,2})",
                    question,
                )
                previous_location = match.group(1).strip() if match else "Pune"

        except KeyboardInterrupt:
            print("\nSystem stopped.")
            break

        except Exception as exc:
            print(f"\nERROR: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
