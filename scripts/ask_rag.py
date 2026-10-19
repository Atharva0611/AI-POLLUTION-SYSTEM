import os
import sys


# Add project root to Python path
PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from backend.rag.rag_pipeline import answer_question


def main():

    print("\n==============================================")
    print("       PUNE AIR POLLUTION RAG SYSTEM")
    print("==============================================")

    print("\nType your question.")
    print("Type 'exit' to close.\n")

    while True:

        question = input("Question: ").strip()

        if question.lower() == "exit":
            print("\nRAG system closed.")
            break

        if not question:
            print("Please enter a question.\n")
            continue

        try:

            result = answer_question(
                question=question,
                k=5
            )

            print("\n==============================================")
            print("ANSWER")
            print("==============================================")

            print(result["answer"])

            print("\n==============================================")
            print("SOURCES")
            print("==============================================")

            for source in result.get("sources", []):

                print(
                    f"File : {source.get('file', 'Unknown')}"
                )

                print(
                    f"Page : {source.get('page', 'Unknown')}"
                )

                print("----------------------------------------------")

        except Exception as e:

            print("\nERROR:")
            print(e)


if __name__ == "__main__":
    main()