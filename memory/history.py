"""Small, JSON-backed conversation history shared by the terminal and UI."""
import json
import os
import tempfile


HISTORY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory", "history.json")
MAX_MESSAGES = 10


def load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH, "r", encoding="utf-8") as file:
        history = json.load(file)
    if not isinstance(history, list):
        raise ValueError(f"Conversation history must be a JSON list: {HISTORY_PATH}")
    return history[-MAX_MESSAGES:]


def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(HISTORY_PATH), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(history[-MAX_MESSAGES:], file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temp_path, HISTORY_PATH)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def clear_history():
    save_history([])


def append_exchange(history, user, assistant):
    updated = list(history)
    updated.extend(
        [
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    )
    return updated[-MAX_MESSAGES:]
