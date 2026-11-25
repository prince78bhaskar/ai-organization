"""Persistent, per-conversation storage for the Streamlit interface."""
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHATS_PATH = ROOT / "memory" / "chats.json"
LEGACY_HISTORY_PATH = ROOT / "memory" / "history.json"


def _timestamp():
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _empty_store():
    return {"version": 1, "legacy_imported": False, "chats": []}


def _validate_store(data):
    if not isinstance(data, dict) or not isinstance(data.get("chats"), list):
        raise ValueError("Chat store must contain a chats list.")

    chats = data["chats"]
    for chat in chats:
        if not isinstance(chat, dict):
            raise ValueError("Chat entries must be objects.")
        if not all(isinstance(chat.get(field), str) for field in ("id", "title")):
            raise ValueError("Chat entries must have string id and title fields.")
        if not isinstance(chat.get("messages"), list):
            raise ValueError("Chat entries must contain a messages list.")
        for message in chat["messages"]:
            if not isinstance(message, dict) or not isinstance(message.get("content"), str):
                raise ValueError("Chat messages must contain string content.")
            if message.get("role") not in ("user", "assistant"):
                raise ValueError("Chat messages must have a valid role.")
            message.setdefault("agents_used", [])
            message.setdefault("steps", [])
            message.setdefault("events", [])

        chat.setdefault("created_at", _timestamp())
        chat.setdefault("updated_at", chat["created_at"])

    return {
        "version": 1,
        "legacy_imported": bool(data.get("legacy_imported", False)),
        "chats": chats,
    }


def save_store(store, path=None):
    """Write the full chat store atomically."""
    path = Path(path or CHATS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(store, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_path, path)
    except Exception:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        raise


def _backup_corrupt_store(path):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = path.with_name(f"{path.name}.corrupt-{stamp}.bak")
    shutil.copy2(path, backup_path)
    return backup_path


def _import_legacy_history(store, path):
    path = Path(path)
    if not path.exists():
        store["legacy_imported"] = True
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            history = json.load(file)
        if not isinstance(history, list):
            raise ValueError("Legacy history must be a JSON list.")

        messages = []
        for item in history:
            if not isinstance(item, dict):
                continue
            role, content = item.get("role"), item.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                messages.append(
                    {
                        "role": role,
                        "content": content,
                        "agents_used": [],
                        "steps": [],
                        "events": [],
                    }
                )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        return f"Purani chat history import nahi hui; original file safe rakhi hai. Details: {error}"

    if messages:
        timestamp = _timestamp()
        store["chats"].append(
            {
                "id": uuid.uuid4().hex,
                "title": "Old chat",
                "created_at": timestamp,
                "updated_at": timestamp,
                "messages": messages,
            }
        )
    store["legacy_imported"] = True
    return None


def load_store(path=None, legacy_path=None):
    """Load chats, back up a corrupt store, and import the old history once."""
    path = Path(path or CHATS_PATH)
    legacy_path = Path(legacy_path or LEGACY_HISTORY_PATH)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as file:
                store = _validate_store(json.load(file))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            _backup_corrupt_store(path)
            store = _empty_store()
            save_store(store, path)
    else:
        store = _empty_store()

    import_warning = None
    if not store["legacy_imported"]:
        import_warning = _import_legacy_history(store, legacy_path)
        if import_warning is None:
            save_store(store, path)
    return store, import_warning


def create_chat():
    timestamp = _timestamp()
    return {
        "id": uuid.uuid4().hex,
        "title": "New chat",
        "created_at": timestamp,
        "updated_at": timestamp,
        "messages": [],
    }


def add_message(chat, message):
    """Append a message and update the conversation title and timestamp."""
    saved_message = {
        "role": message["role"],
        "content": message["content"],
        "agents_used": list(message.get("agents_used", [])),
        "steps": list(message.get("steps", [])),
        "events": list(message.get("events", [])),
    }
    if message.get("error_details"):
        saved_message["error_details"] = message["error_details"]
    chat["messages"].append(saved_message)
    chat["updated_at"] = _timestamp()

    if chat["title"] == "New chat" and saved_message["role"] == "user":
        first_line = " ".join(saved_message["content"].split())
        chat["title"] = first_line if len(first_line) <= 30 else first_line[:27] + "..."


def delete_chat(store, chat_id):
    store["chats"] = [chat for chat in store["chats"] if chat["id"] != chat_id]


def delete_all_chats(store):
    store["chats"] = []


def sorted_chats(store):
    return sorted(store["chats"], key=lambda chat: chat["updated_at"], reverse=True)
