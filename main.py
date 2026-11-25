"""AI Organization - terminal chat.

Chalao:  python main.py
Commands:
  /ingest <file ya folder>   documents ko RAG database mein daalo
  /steps                     har agent ka beech ka output dikhana on/off
  /quit                      bahar niklo
"""
import os

from agents import rag
from orchestrator import handle


def main():
    show_steps = False
    print("=== AI Organization === (task likho, ya /ingest <path>, /steps, /quit)\n")
    while True:
        try:
            task = input("Tum: ").strip().strip('"')
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not task:
            continue
        if task == "/quit":
            break
        if task == "/steps":
            show_steps = not show_steps
            print(f"Steps dikhana: {'ON' if show_steps else 'OFF'}\n")
            continue
        if task.startswith("/ingest"):
            path = task[len("/ingest"):].strip().strip('"')
            if not os.path.exists(path):
                print("Ye path nahi mila.\n")
                continue
            try:
                print(rag.ingest(path), "\n")
            except Exception as e:
                print(f"Ingest fail: {e}\n")
            continue

        try:
            answer, steps = handle(task, on_step=lambda m: print(f"  · {m}"))
        except Exception as e:
            print(f"Error: {e}\n(Ollama chal raha hai? `ollama list` check karo)\n")
            continue

        if show_steps and len(steps) > 1:
            for name, out in steps[:-1]:
                print(f"\n--- {name} ka output ---\n{out}")
        print(f"\nAI Organization:\n{answer}\n")


if __name__ == "__main__":
    main()
