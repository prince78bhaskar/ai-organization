"""Focused tests for Streamlit chat persistence."""
import json
import tempfile
import unittest
from pathlib import Path

from ui.storage import (
    add_message,
    create_chat,
    delete_all_chats,
    delete_chat,
    load_store,
    save_store,
    sorted_chats,
)


class ChatStorageTests(unittest.TestCase):
    def test_imports_legacy_history_once_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as directory:
            chats_path = Path(directory) / "chats.json"
            legacy_path = Path(directory) / "history.json"
            original = [{"role": "user", "content": "A previous question"}]
            legacy_path.write_text(json.dumps(original), encoding="utf-8")

            store, warning = load_store(chats_path, legacy_path)
            imported_bytes = legacy_path.read_bytes()
            reloaded, second_warning = load_store(chats_path, legacy_path)

            self.assertIsNone(warning)
            self.assertIsNone(second_warning)
            self.assertEqual(len(store["chats"]), 1)
            self.assertEqual(store["chats"][0]["title"], "Old chat")
            self.assertEqual(store["chats"], reloaded["chats"])
            self.assertEqual(imported_bytes, legacy_path.read_bytes())

    def test_corrupt_store_is_backed_up_before_fresh_store_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            chats_path = Path(directory) / "chats.json"
            chats_path.write_text("{bad json", encoding="utf-8")

            store, _ = load_store(chats_path, Path(directory) / "missing-history.json")

            backups = list(Path(directory).glob("chats.json.corrupt-*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "{bad json")
            self.assertEqual(store["chats"], [])
            self.assertEqual(json.loads(chats_path.read_text(encoding="utf-8"))["chats"], [])

    def test_chat_title_updates_and_delete_operations_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "chats.json"
            store = {"version": 1, "legacy_imported": True, "chats": []}
            first_chat = create_chat()
            second_chat = create_chat()
            store["chats"].extend([first_chat, second_chat])
            add_message(first_chat, {"role": "user", "content": "A title that is longer than thirty characters"})
            self.assertEqual(len(first_chat["title"]), 30)

            delete_chat(store, second_chat["id"])
            save_store(store, path)
            loaded, _ = load_store(path, Path(directory) / "missing-history.json")
            self.assertEqual([chat["id"] for chat in sorted_chats(loaded)], [first_chat["id"]])

            delete_all_chats(loaded)
            self.assertEqual(loaded["chats"], [])


if __name__ == "__main__":
    unittest.main()
