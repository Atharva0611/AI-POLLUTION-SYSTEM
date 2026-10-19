import os
import re
import pickle
import requests

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer


ROOT = r"C:\final year project\AI-POLLUTION-SYSTEM"

DOC_DIR = os.path.join(
    ROOT,
    "backend",
    "rag",
    "documents"
)

STORE_DIR = os.path.join(
    ROOT,
    "backend",
    "rag",
    "store"
)

os.makedirs(
    DOC_DIR,
    exist_ok=True
)

os.makedirs(
    STORE_DIR,
    exist_ok=True
)


# ============================================================
# OFFICIAL CPCB DOCUMENTS
# ============================================================

DOCUMENTS = {
    "cpcb_naaqs.pdf":
        "https://cpcb.nic.in/upload/NAAQS_2019.pdf",

    "pune_action_plan.pdf":
        "https://cpcb.nic.in/Actionplan/Pune.pdf",
}


# ============================================================
# STORE FILES
# ============================================================

VECTOR_FILE = os.path.join(
    STORE_DIR,
    "tfidf_vectorizer.pkl"
)

MATRIX_FILE = os.path.join(
    STORE_DIR,
    "tfidf_matrix.pkl"
)

CHUNKS_FILE = os.path.join(
    STORE_DIR,
    "chunks.pkl"
)


# ============================================================
# DOWNLOAD
# ============================================================

headers = {
    "User-Agent":
        "AI-Pollution-System/1.0"
}


for filename, url in DOCUMENTS.items():

    path = os.path.join(
        DOC_DIR,
        filename
    )

    if os.path.exists(path) and os.path.getsize(path) > 1000:

        print(
            f"[OK] {filename} already exists"
        )

        continue

    print(
        f"[DOWNLOAD] {filename}"
    )

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=60
        )

        response.raise_for_status()

        if len(response.content) < 1000:

            raise RuntimeError(
                "Downloaded file is too small."
            )

        with open(
            path,
            "wb"
        ) as f:

            f.write(
                response.content
            )

        print(
            f"[SAVED] {path}"
        )

    except Exception as exc:

        print(
            f"[WARNING] Could not download {filename}: {exc}"
        )


# ============================================================
# FIND PDF FILES IN BOTH DOCUMENT LOCATIONS
# ============================================================

RAG_DATA_DIR = os.path.join(ROOT, "rag_data")
pdf_files = []
seen_paths = set()

for search_dir in (DOC_DIR, RAG_DATA_DIR):
    if not os.path.isdir(search_dir):
        print(f"[SKIP] Directory not found: {search_dir}")
        continue

    for current_root, _, filenames in os.walk(search_dir):
        for filename in filenames:
            if not filename.lower().endswith(".pdf"):
                continue

            path = os.path.abspath(
                os.path.join(current_root, filename)
            )
            normalized_path = os.path.normcase(path)

            if normalized_path in seen_paths:
                continue

            if os.path.getsize(path) > 1000:
                pdf_files.append(path)
                seen_paths.add(normalized_path)
                print(f"[FOUND] {path}")


if not pdf_files:

    raise FileNotFoundError(
        "No usable PDF documents found in:\n"
        + DOC_DIR
        + "\nDownload failed for all documents."
    )


print()
print(
    "=" * 70
)
print(
    "BUILDING RAG KNOWLEDGE BASE"
)
print(
    "=" * 70
)

print(
    "PDF files:",
    len(pdf_files)
)


# ============================================================
# CHUNK FUNCTION
# ============================================================

def clean_text(text):

    text = text.replace(
        "\x00",
        " "
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def make_chunks(
    text,
    size=1200,
    overlap=200
):

    text = clean_text(
        text
    )

    if not text:
        return []

    chunks = []

    start = 0

    while start < len(text):

        end = min(
            start + size,
            len(text)
        )

        chunk = text[
            start:end
        ].strip()

        if len(chunk) >= 100:

            chunks.append(
                chunk
            )

        if end >= len(text):

            break

        start = end - overlap

    return chunks


# ============================================================
# EXTRACT PDFs
# ============================================================

all_chunks = []

for path in pdf_files:

    filename = os.path.basename(
        path
    )

    print(
        f"[PROCESS] {filename}"
    )

    try:

        reader = PdfReader(
            path
        )

        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):

            try:

                text = page.extract_text() or ""

            except Exception:

                text = ""

            for chunk_id, chunk in enumerate(
                make_chunks(text)
            ):

                all_chunks.append({
                    "text": chunk,
                    "source": filename,
                    "page": page_number,
                    "chunk_id": chunk_id
                })

    except Exception as exc:

        print(
            f"[WARNING] {filename}: {exc}"
        )


if not all_chunks:

    raise RuntimeError(
        "PDFs were found, but no readable text "
        "could be extracted."
    )


print(
    "\nTotal chunks:",
    len(all_chunks)
)


# ============================================================
# TF-IDF VECTOR STORE
# ============================================================

texts = [
    item["text"]
    for item in all_chunks
]


vectorizer = TfidfVectorizer(
    lowercase=True,
    stop_words="english",
    ngram_range=(1, 2),
    min_df=1,
    max_df=0.98,
)


matrix = vectorizer.fit_transform(
    texts
)


with open(
    VECTOR_FILE,
    "wb"
) as f:

    pickle.dump(
        vectorizer,
        f
    )


with open(
    MATRIX_FILE,
    "wb"
) as f:

    pickle.dump(
        matrix,
        f
    )


with open(
    CHUNKS_FILE,
    "wb"
) as f:

    pickle.dump(
        all_chunks,
        f
    )


print()
print(
    "=" * 70
)
print(
    "RAG BUILD COMPLETE"
)
print(
    "=" * 70
)

print(
    "Vectorizer:",
    VECTOR_FILE
)

print(
    "Matrix:",
    MATRIX_FILE
)

print(
    "Chunks:",
    CHUNKS_FILE
)

print(
    "Matrix shape:",
    matrix.shape
)
