"""Read-only access to the document chunks stored by the RAG agent."""

import logging
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import chromadb

import config
from llm import embed


ROOT = Path(__file__).resolve().parents[1]
UPLOADS_DIR = ROOT / "uploads"
_LOGGER = logging.getLogger("ai_organization.web.sources")
_SAFE_FILE = re.compile(r"^[A-Za-z0-9._-]{1,200}$")
_UPLOAD_PREFIX = re.compile(r"^[0-9a-f]{32}_", re.IGNORECASE)


def _chroma_path(chroma_dir=None):
    path = Path(chroma_dir or config.CHROMA_DIR)
    return path if path.is_absolute() else ROOT / path


def _collection(chroma_dir=None):
    path = _chroma_path(chroma_dir)
    if not path.is_dir() or not (path / "chroma.sqlite3").is_file():
        return None
    client = chromadb.PersistentClient(path=str(path))
    collections = client.list_collections()
    if not any(getattr(item, "name", item) == "docs" for item in collections):
        return None
    return client.get_collection("docs")


def _safe_file(file):
    if (
        not isinstance(file, str)
        or not _SAFE_FILE.fullmatch(file)
        or file in (".", "..")
        or Path(file).name != file
    ):
        raise ValueError("Invalid document name.")
    return file


def _display_name(file):
    return _UPLOAD_PREFIX.sub("", file, count=1)


def retrieve_sources(question, chroma_dir=None):
    """Return the same nearest chunks used for RAG, without changing Chroma."""
    collection = _collection(chroma_dir)
    if collection is None:
        return []
    count = collection.count()
    if not count:
        return []

    vectors = embed(config.EMBED_MODEL, [question])
    results = collection.query(
        query_embeddings=vectors,
        n_results=min(config.RAG_TOP_K, count),
        include=["documents", "metadatas", "distances"],
    )
    ids = results.get("ids") or [[]]
    documents = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]
    sources = []
    for chunk_id, text, metadata, distance in zip(
        ids[0], documents[0], metadatas[0], distances[0]
    ):
        if not metadata or not isinstance(text, str) or distance is None:
            continue
        sources.append(
            {
                "file": metadata["file"],
                "page": metadata["page"],
                "text": text,
                "score": 1 - distance,
                "chunk_id": chunk_id,
            }
        )
    return sources


def list_documents(chroma_dir=None, uploads_dir=UPLOADS_DIR):
    collection = _collection(chroma_dir)
    if collection is None:
        return []
    count = collection.count()
    if not count:
        return []
    records = collection.get(include=["metadatas"], limit=count)
    grouped = defaultdict(list)
    for metadata in records.get("metadatas") or []:
        if metadata and isinstance(metadata.get("file"), str):
            grouped[metadata["file"]].append(metadata.get("page"))

    documents = []
    for file, pages in grouped.items():
        uploaded_at = None
        try:
            stat = (Path(uploads_dir) / _safe_file(file)).stat()
            uploaded_at = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(
                timespec="seconds"
            )
        except (OSError, ValueError):
            _LOGGER.info("Original upload is unavailable for ingested document %s.", file)
        documents.append(
            {
                "file": file,
                "name": _display_name(file),
                "pages": len(set(pages)),
                "chunks": len(pages),
                "uploaded_at": uploaded_at,
            }
        )
    return sorted(documents, key=lambda item: item["name"].casefold())


def get_document(file, chroma_dir=None):
    file = _safe_file(file)
    collection = _collection(chroma_dir)
    if collection is None or not collection.count():
        return None
    records = collection.get(
        where={"file": file},
        include=["documents", "metadatas"],
    )
    if not records.get("ids"):
        return None

    grouped = defaultdict(list)
    chunks = []
    for chunk_id, text, metadata in zip(
        records["ids"], records.get("documents") or [], records.get("metadatas") or []
    ):
        if not metadata or not isinstance(text, str):
            continue
        page = metadata.get("page", "unknown")
        suffix = chunk_id.rsplit("|", 1)[-1]
        try:
            chunk_index = int(suffix)
        except ValueError:
            chunk_index = 0
        grouped[page].append((chunk_index, text))
        chunks.append({"page": page, "text": text, "chunk_id": chunk_id})

    pages = []
    for page, page_chunks in grouped.items():
        page_chunks.sort(key=lambda item: item[0])
        text = page_chunks[0][1]
        for _, chunk in page_chunks[1:]:
            text += chunk[min(120, len(chunk)) :]
        pages.append({"page": page, "text": text})

    def page_order(item):
        match = re.search(r"\d+", str(item["page"]))
        return (0, int(match.group())) if match else (1, str(item["page"]).casefold())

    def chunk_order(item):
        suffix = item["chunk_id"].rsplit("|", 1)[-1]
        try:
            return page_order(item), int(suffix)
        except ValueError:
            return page_order(item), 0

    pages.sort(key=page_order)
    chunks.sort(key=chunk_order)
    return {
        "file": file,
        "name": _display_name(file),
        "pages": pages,
        "chunks": chunks,
    }


def delete_document(file, chroma_dir=None, uploads_dir=UPLOADS_DIR):
    file = _safe_file(file)
    collection = _collection(chroma_dir)
    if collection is None or not collection.count():
        return False
    existing = collection.get(where={"file": file}, include=["metadatas"])
    if not existing.get("ids"):
        return False

    collection.delete(where={"file": file})
    upload_path = Path(uploads_dir) / file
    try:
        upload_root = Path(uploads_dir).resolve()
        resolved_upload = upload_path.resolve()
        if os.path.commonpath([str(upload_root), str(resolved_upload)]) != str(upload_root):
            raise ValueError("Invalid document path.")
        if resolved_upload.is_file():
            resolved_upload.unlink()
    except OSError:
        _LOGGER.exception("Removed document chunks but could not delete upload %s.", file)
        raise
    return True
