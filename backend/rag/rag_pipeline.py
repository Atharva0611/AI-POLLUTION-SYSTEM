import os

from dotenv import load_dotenv

from langchain_google_genai import (
    ChatGoogleGenerativeAI
)

from .retriever import search_documents


CURRENT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_ROOT = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "..")
)

ENV_FILE = os.path.join(
    PROJECT_ROOT,
    ".env"
)

load_dotenv(ENV_FILE)


def answer_question(question: str, k: int = 5):

    documents = search_documents(
        query=question,
        k=k
    )

    if not documents:
        return {
            "answer": "No relevant information found.",
            "sources": []
        }

    context = "\n\n".join(
        [
            f"DOCUMENT {i + 1}:\n{doc.page_content}"
            for i, doc in enumerate(documents)
        ]
    )

    sources = [
        {
            "file": doc.metadata.get(
                "file_name",
                "Unknown"
            ),
            "page": doc.metadata.get(
                "page",
                "Unknown"
            )
        }
        for doc in documents
    ]

    api_key = os.getenv(
        "GOOGLE_API_KEY"
    )

    if not api_key:
        raise ValueError(
            f"GOOGLE_API_KEY not found in {ENV_FILE}"
        )

    model_name = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash"
    )

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0,
        google_api_key=api_key
    )

    prompt = f"""
You are an AI assistant for a Pune air-pollution
analysis system.

Answer ONLY from the retrieved documents.

Do not invent facts.

If the documents do not contain enough information,
say that clearly.

Question:
{question}

Retrieved documents:
{context}

Answer:
"""

    response = llm.invoke(prompt)

    return {
        "answer": response.content,
        "sources": sources
    }


if __name__ == "__main__":

    print("\n=== PUNE AIR POLLUTION RAG ===")

    question = input(
        "Ask your question: "
    )

    result = answer_question(question)

    print("\n=== ANSWER ===\n")
    print(result["answer"])

    print("\n=== SOURCES ===")

    for source in result["sources"]:
        print(
            source["file"],
            "| page:",
            source["page"]
        )