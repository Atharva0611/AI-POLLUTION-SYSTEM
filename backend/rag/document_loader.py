import os

from langchain_community.document_loaders import PyPDFLoader


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = os.path.abspath(
    os.path.join(CURRENT_DIR, "..", "..")
)

RAG_DATA_DIR = os.path.join(
    PROJECT_ROOT,
    "rag_data"
)


def load_documents():

    documents = []

    if not os.path.exists(RAG_DATA_DIR):
        raise FileNotFoundError(
            f"RAG folder not found: {RAG_DATA_DIR}"
        )

    for root, _, files in os.walk(RAG_DATA_DIR):

        for file in files:

            if not file.lower().endswith(".pdf"):
                continue

            file_path = os.path.join(root, file)

            print("Loading:", file_path)

            loader = PyPDFLoader(file_path)

            docs = loader.load()

            category = os.path.basename(root)

            for doc in docs:
                doc.metadata["file_name"] = file
                doc.metadata["category"] = category
                doc.metadata["full_path"] = file_path

            documents.extend(docs)

    print(f"Total pages loaded: {len(documents)}")

    return documents


if __name__ == "__main__":
    docs = load_documents()
    print("Loaded:", len(docs))