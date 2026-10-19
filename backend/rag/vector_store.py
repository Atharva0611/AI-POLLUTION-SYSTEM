import os
import shutil

from langchain_chroma import Chroma

from .document_loader import load_documents
from .text_splitter import split_documents
from .embeddings import get_embeddings


CURRENT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PROJECT_ROOT = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "..")
)

CHROMA_DIR = os.path.join(
    PROJECT_ROOT,
    "vector_db",
    "chroma"
)

COLLECTION_NAME = "pune_pollution_knowledge"


def create_vector_store(reset=False):

    if reset and os.path.exists(CHROMA_DIR):
        print("Removing old ChromaDB...")
        shutil.rmtree(CHROMA_DIR)

    print("\nLoading documents...")
    documents = load_documents()

    if not documents:
        raise ValueError(
            "No PDF files found in rag_data."
        )

    print("\nSplitting documents...")
    chunks = split_documents(documents)

    if not chunks:
        raise ValueError(
            "No chunks created."
        )

    print("\nCreating embeddings...")
    embeddings = get_embeddings()

    print("\nCreating ChromaDB...")

    os.makedirs(
        CHROMA_DIR,
        exist_ok=True
    )

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME
    )

    print("\nChromaDB created successfully")
    print("Location:", CHROMA_DIR)
    print("Chunks:", len(chunks))

    return vector_store


def get_vector_store():

    if not os.path.exists(CHROMA_DIR):
        raise FileNotFoundError(
            f"ChromaDB not found at:\n{CHROMA_DIR}\n"
            "Build it first."
        )

    embeddings = get_embeddings()

    vector_store = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME
    )

    return vector_store


if __name__ == "__main__":
    create_vector_store(reset=False)