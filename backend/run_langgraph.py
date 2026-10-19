from backend.agents.orchestrator import app


print("=" * 70)
print("AI POLLUTION LANGGRAPH ASSISTANT")
print("=" * 70)
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
            "\nAssistant: Analyzing..."
        )

        result = app.invoke(
            {
                "question": question
            }
        )

        print()

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
            "\nERROR:"
        )

        print(
            exc
        )

        print(
            "\n" + "-" * 70 + "\n"
        )
