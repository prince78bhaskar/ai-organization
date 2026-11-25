"""RAG Agent: documents ingest karo (ChromaDB) aur unke basis par jawab do."""
import os

import chromadb

from config import CHROMA_DIR, EMBED_MODEL, RAG_TOP_K, STUDY_MODEL
from llm import chat, embed
from tools.doc_reader import IMAGE_EXT, TEXT_EXT, read_document

SYSTEM = """You are the RAG Agent of an AI Organization.
Answer ONLY from the provided document excerpts.
Rules:
- Reply in the user's language.
- Mention the source like (file, page) after each fact.
- If the answer is not in the excerpts, say clearly: "Ye jawab documents mein nahi mila."
- Never make up information."""

_client = None


def _collection():
    global _client
    if _client is None:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _client.get_or_create_collection("docs", metadata={"hnsw:space": "cosine"})


def _chunk(text: str, size: int = 800, overlap: int = 120):
    text = text.strip()
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return [c for c in chunks if c.strip()]


def ingest(path: str) -> str:
    """File ya folder ko database mein daalo."""
    if os.path.isdir(path):
        total = 0
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            ext = os.path.splitext(name)[1].lower()
            if os.path.isfile(full) and ext in (IMAGE_EXT | TEXT_EXT | {".pdf"}):
                total += _ingest_file(full)
        return f"Folder se {total} chunks save hue."
    return f"{_ingest_file(path)} chunks save hue."


def _ingest_file(path: str) -> int:
    fname = os.path.basename(path)
    ids, docs, metas = [], [], []
    for label, text in read_document(path):
        for j, ch in enumerate(_chunk(text)):
            ids.append(f"{fname}|{label}|{j}")
            docs.append(ch)
            metas.append({"file": fname, "page": label})
    if not docs:
        return 0
    vectors = embed(EMBED_MODEL, docs)
    _collection().upsert(ids=ids, documents=docs, embeddings=vectors, metadatas=metas)
    return len(docs)


def has_documents() -> bool:
    try:
        return _collection().count() > 0
    except Exception:
        return False


def run(task: str, context: str = "") -> str:
    col = _collection()
    if col.count() == 0:
        return "Abhi koi document ingest nahi hua. Pehle `/ingest <file ya folder path>` chalao."

    qvec = embed(EMBED_MODEL, [task])
    res = col.query(query_embeddings=qvec, n_results=min(RAG_TOP_K, col.count()))
    excerpts = []
    for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
        excerpts.append(f"[{meta['file']}, {meta['page']}]\n{doc}")

    user = "Document excerpts:\n\n" + "\n\n".join(excerpts) + f"\n\nQuestion: {task}"
    if context:
        user = f"Extra context:\n{context}\n\n" + user
    return chat(STUDY_MODEL, SYSTEM, user, temperature=0.1)
