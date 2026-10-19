from langchain_text_splitters import RecursiveCharacterTextSplitter

from .document_loader import load_documents


def split_documents(documents):

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            ""
        ]
    )

    chunks = splitter.split_documents(documents)

    print("Total chunks:", len(chunks))

    return chunks


if __name__ == "__main__":

    documents = load_documents()

    chunks = split_documents(documents)

    if chunks:
        print("\nFirst chunk:\n")
        print(chunks[0].page_content)