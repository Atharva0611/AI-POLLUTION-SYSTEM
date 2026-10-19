import os
import pickle
from pathlib import Path

from sklearn.metrics.pairwise import cosine_similarity
from langchain_core.documents import Document


ROOT = Path(__file__).resolve().parents[2]

STORE_DIR = ROOT / "backend" / "rag" / "store"

VECTOR_FILE = STORE_DIR / "tfidf_vectorizer.pkl"
MATRIX_FILE = STORE_DIR / "tfidf_matrix.pkl"
CHUNKS_FILE = STORE_DIR / "chunks.pkl"


def load_store():

    if not VECTOR_FILE.exists():
        raise FileNotFoundError(
            f"Missing: {VECTOR_FILE}"
        )

    if not MATRIX_FILE.exists():
        raise FileNotFoundError(
            f"Missing: {MATRIX_FILE}"
        )

    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(
            f"Missing: {CHUNKS_FILE}"
        )

    with open(VECTOR_FILE, "rb") as f:
        vectorizer = pickle.load(f)

    with open(MATRIX_FILE, "rb") as f:
        matrix = pickle.load(f)

    with open(CHUNKS_FILE, "rb") as f:
        chunks = pickle.load(f)

    return vectorizer, matrix, chunks


def retrieve(
    query,
    top_k=5
):

    vectorizer, matrix, chunks = load_store()

    query_vector = vectorizer.transform(
        [query]
    )

    scores = cosine_similarity(
        query_vector,
        matrix
    )[0]

    indices = scores.argsort()[::-1][:top_k]

    results = []

    for index in indices:

        item = chunks[index]

        results.append({
            "score": float(
                scores[index]
            ),
            "text": item.get(
                "text",
                ""
            ),
            "source": item.get(
                "source",
                item.get(
                    "file",
                    "unknown"
                )
            ),
            "page": item.get(
                "page"
            ),
            "chunk_id": item.get(
                "chunk_id"
            )
        })

    return results


def search_documents(query: str, k: int = 5):
    """Return retrieved chunks as LangChain Document objects."""

    results = retrieve(query, top_k=k)

    documents = []

    for result in results:
        documents.append(
            Document(
                page_content=result.get("text", ""),
                metadata={
                    "file_name": result.get("source", "Unknown"),
                    "page": result.get("page", "Unknown"),
                    "score": result.get("score", 0.0),
                    "chunk_id": result.get("chunk_id")
                }
            )
        )

    return documents


if __name__ == "__main__":

    question = input(
        "Policy question: "
    ).strip()

    results = retrieve(
        question,
        top_k=5
    )

    for i, result in enumerate(
        results,
        start=1
    ):

        print(
            "\n" + "=" * 70
        )

        print(
            f"RESULT {i}"
        )

        print(
            f"Score: {result['score']:.4f}"
        )

        print(
            f"Source: {result['source']}"
        )

        print(
            f"Page: {result['page']}"
        )

        print(
            result["text"][:1000]
        )
