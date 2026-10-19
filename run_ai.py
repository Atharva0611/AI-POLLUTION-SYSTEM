from backend.agents.orchestrator import run_pipeline
import uuid
import traceback

def main():
    session_id = str(uuid.uuid4())

    print("\n" + "=" * 60)
    print("       ORIVA - AI POLLUTION INTELLIGENCE CHATBOT")
    print("=" * 60)
    print("Ask about AQI, CPCB, PM2.5, forecasts, DBSCAN, SHAP,")
    print("pollution policies, RAG, weather, or recommendations.")
    print("Type 'exit' to quit.")
    print("=" * 60)

    while True:
        try:
            question = input("\nYou: ").strip()

            if question.lower() in {"exit", "quit", "bye"}:
                print("\nAI: Goodbye!")
                break

            if not question:
                continue

            state = {
                "question": question,
                "session_id": session_id
            }

            result = run_pipeline(state)

            answer = result.get("final_answer")

            if answer:
                print("\nAI:", answer)
            else:
                print("\nAI: No answer was returned by the graph.")

        except KeyboardInterrupt:
            print("\n\nAI: Chat ended.")
            break

        except Exception as exc:
            print(f"\nAI: Error processing your question: {exc}")
            traceback.print_exc()

if __name__ == "__main__":
    main()
