from backend.agents.final_agent import app


print("=" * 70)
print("AI POLLUTION FINAL AGENT")
print("=" * 70)
print("WeatherAPI + XGBoost + Ensemble + Anomaly + DBSCAN")
print("RAG + Policy + Recommendations + LangGraph")
print("Type 'exit' to stop.")
print()


while True:

    try:

        question = input(
            "You: "
        ).strip()

        if not question:
            continue

        if question.lower() in {
            "exit",
            "quit",
            "q",
            "bye"
        }:

            print(
                "\nAssistant: Goodbye!"
            )

            break

        print(
            "\nAssistant: Analyzing...\n"
        )

        result = app.invoke(
            {
                "question": question
            }
        )

        print(
            result.get(
                "final_answer",
                "No answer generated."
            )
        )

        print(
            "\n" + "=" * 70 + "\n"
        )

    except KeyboardInterrupt:

        print(
            "\nAssistant: Exiting..."
        )

        break

    except Exception as exc:

        print(
            "\nAssistant ERROR:"
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print(
            "\n" + "-" * 70 + "\n"
        )
