from langchain_huggingface import HuggingFaceEmbeddings


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )


if __name__ == "__main__":
    print("Loading embedding model...")

    embeddings = get_embeddings()

    test_vector = embeddings.embed_query(
        "PM2.5 pollution in Pune"
    )

    print("Embedding working")
    print("Dimensions:", len(test_vector))