"""Master Orchestrator: task padhta hai, agents chunta hai, unhe chalata hai."""
import json

from agents import coding, rag, research, study
from config import ORCHESTRATOR_MODEL
from llm import chat

AGENTS = {
    "coding": coding.run,
    "research": research.run,
    "study": study.run,
    "rag": rag.run,
}

ROUTER_SYSTEM = """You are the Master Orchestrator of an AI Organization.
Pick which specialist agents should handle the user's task, in the order they should run.

Agents:
- coding: write/debug/test code, programming help
- research: search the internet, verify facts, make reports on current topics
- study: explain concepts, make notes, quizzes, exam preparation
- rag: answer questions using the user's uploaded documents (PDF, scans, images, handwritten notes)

Rules:
- Use 1 agent when possible. Use 2-3 only when the task clearly needs a pipeline
  (example: "research X and make quiz" -> ["research","study"]).
- Use "rag" ONLY if the task is about the user's own documents/files.
- Output ONLY JSON: {"agents": ["..."], "plan": "one short line in the user's language"}"""

KEYWORDS = {
    "coding": ["code", "python", "bug", "error", "function", "script", "program", "javascript", "sql", "debug"],
    "research": ["research", "latest", "news", "internet", "search", "report", "compare", "verify", "2025", "2026"],
    "study": ["explain", "samjha", "notes", "quiz", "exam", "revise", "concept", "mcq", "padhai"],
    "rag": ["document", "pdf", "file", "upload", "image", "scan", "handwritten", "notes mein"],
}


def _fallback(task: str):
    t = task.lower()
    scores = {a: sum(k in t for k in kws) for a, kws in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return [best if scores[best] > 0 else "study"]


def route(task: str):
    """Returns (agents_list, plan_text)."""
    try:
        raw = chat(ORCHESTRATOR_MODEL, ROUTER_SYSTEM, task, as_json=True, temperature=0.0)
        data = json.loads(raw)
        agents = [a for a in data.get("agents", []) if a in AGENTS][:3]
        plan = str(data.get("plan", ""))
        if agents:
            return agents, plan
    except Exception:
        pass
    return _fallback(task), "(router fail hua, keyword se agent chuna)"


def handle(task: str, on_step=None):
    """Poora task chalao. on_step(msg) se progress dikha sakte ho.
    Returns (final_answer, steps) jahan steps = [(agent, output), ...]"""
    say = on_step or (lambda m: None)

    agents, plan = route(task)
    say(f"Plan: {plan}")
    say(f"Agents: {' -> '.join(agents)}")

    steps, context = [], ""
    for name in agents:
        say(f"[{name}] kaam kar raha hai...")
        try:
            out = AGENTS[name](task, context)
        except Exception as e:
            out = f"{name} agent mein error: {e}"
        steps.append((name, out))
        context = out  # agla agent isi ke upar kaam karega

    return steps[-1][1], steps
