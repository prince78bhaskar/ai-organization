"""Per-chat JSON storage for the local web application."""

import json
import logging
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHATS_DIR = ROOT / "memory" / "web_chats"
LEGACY_CHATS_PATH = ROOT / "memory" / "chats.json"
_IMPORT_MARKER = CHATS_DIR / ".legacy_imported"
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_LOCK = threading.RLock()
_LOGGER = logging.getLogger("ai_organization.web.storage")


def _timestamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _chat_path(chat_id):
    if not isinstance(chat_id, str) or not _ID_PATTERN.fullmatch(chat_id):
        return None
    return CHATS_DIR / f"{chat_id}.json"


def _read_chat(path):
    with path.open("r", encoding="utf-8") as file:
        chat = json.load(file)
    if not isinstance(chat, dict) or not isinstance(chat.get("messages"), list):
        raise ValueError(f"Invalid chat file: {path.name}")
    return chat


def _write_chat(chat):
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    path = _chat_path(chat["id"])
    if path is None:
        raise ValueError("Invalid chat id.")
    descriptor, temporary_path = tempfile.mkstemp(
        dir=str(CHATS_DIR), prefix=f".{chat['id']}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(chat, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_path, path)
    except Exception:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        raise


def _normalize_legacy_chat(source):
    if not isinstance(source, dict):
        return None
    chat_id = source.get("id")
    if not isinstance(chat_id, str) or not _ID_PATTERN.fullmatch(chat_id):
        chat_id = uuid.uuid4().hex
    created_at = source.get("created_at")
    if not isinstance(created_at, str):
        created_at = _timestamp()
    messages = []
    for item in source.get("messages", []):
        if not isinstance(item, dict):
            continue
        role, content = item.get("role"), item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        messages.append(
            {
                "role": role,
                "content": content,
                "agents_used": item.get("agents_used", []),
                "steps": item.get("steps", []),
                "sources": item.get("sources", []),
                "events": item.get("events", []),
                "timestamp": item.get("timestamp", created_at),
            }
        )
    return {
        "id": chat_id,
        "title": source.get("title") if isinstance(source.get("title"), str) else "Old chat",
        "created_at": created_at,
        "updated_at": source.get("updated_at")
        if isinstance(source.get("updated_at"), str)
        else created_at,
        "messages": messages,
    }


def _import_legacy_chats():
    if _IMPORT_MARKER.exists():
        return
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    imported = []
    try:
        if LEGACY_CHATS_PATH.exists():
            with LEGACY_CHATS_PATH.open("r", encoding="utf-8") as file:
                data = json.load(file)
            for entry in data.get("chats", []) if isinstance(data, dict) else []:
                chat = _normalize_legacy_chat(entry)
                if chat is not None:
                    imported.append(chat)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        _LOGGER.warning("Could not import legacy web chats; the original file was left untouched.", exc_info=True)
        return

    for chat in imported:
        if _chat_path(chat["id"]).exists():
            chat["id"] = uuid.uuid4().hex
        _write_chat(chat)
    _IMPORT_MARKER.write_text("done\n", encoding="utf-8")


def list_chats():
    with _LOCK:
        _import_legacy_chats()
        chats = []
        for path in CHATS_DIR.glob("*.json"):
            try:
                chat = _read_chat(path)
                chats.append(
                    {
                        "id": chat["id"],
                        "title": chat.get("title", "New chat"),
                        "updated_at": chat.get("updated_at", ""),
                    }
                )
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
        return sorted(chats, key=lambda chat: chat["updated_at"], reverse=True)


def get_chat(chat_id):
    with _LOCK:
        _import_legacy_chats()
        path = _chat_path(chat_id)
        if path is None or not path.is_file():
            return None
        return _read_chat(path)


def create_chat():
    with _LOCK:
        _import_legacy_chats()
        timestamp = _timestamp()
        chat = {
            "id": uuid.uuid4().hex,
            "title": "New chat",
            "created_at": timestamp,
            "updated_at": timestamp,
            "messages": [],
        }
        _write_chat(chat)
        return chat


def rename_chat(chat_id, title):
    with _LOCK:
        chat = get_chat(chat_id)
        if chat is None:
            return None
        chat["title"] = title.strip()
        chat["updated_at"] = _timestamp()
        _write_chat(chat)
        return chat


def append_message(chat_id, message):
    with _LOCK:
        chat = get_chat(chat_id)
        if chat is None:
            return None
        role = message["role"]
        if role not in ("user", "assistant") or not isinstance(message.get("content"), str):
            raise ValueError("Invalid chat message.")
        timestamp = _timestamp()
        chat["messages"].append(
            {
                "role": role,
                "content": message["content"],
                "agents_used": message.get("agents_used", []),
                "steps": message.get("steps", []),
                "sources": message.get("sources", []),
                "events": message.get("events", []),
                "timestamp": timestamp,
            }
        )
        chat["updated_at"] = timestamp
        if chat["title"] == "New chat" and role == "user":
            title = " ".join(message["content"].split())
            chat["title"] = title if len(title) <= 42 else f"{title[:39]}..."
        _write_chat(chat)
        return chat


def delete_chat(chat_id):
    with _LOCK:
        _import_legacy_chats()
        path = _chat_path(chat_id)
        if path is None or not path.is_file():
            return False
        path.unlink()
        return True


def delete_all_chats():
    with _LOCK:
        _import_legacy_chats()
        for path in CHATS_DIR.glob("*.json"):
            path.unlink()
