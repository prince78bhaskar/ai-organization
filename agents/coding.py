"""Coding Agent: code likho -> chalao -> error aaye to khud fix karo (loop)."""
import re

from config import CODING_MODEL, MAX_FIX_ATTEMPTS
from llm import chat
from tools.code_runner import run_python

SYSTEM = """You are the Coding Agent of an AI Organization.
Write clean, complete, runnable code that solves the task.
Rules:
- Return the full code inside ONE fenced block, e.g. ```python ... ```.
- For Python, the script must run on its own with no user input() and print its result.
- Include a few tests with correct, manually checked expected results. For a prime
  checker, 2 and 17 are prime; 1, 4, and 9 are not.
- When a test fails, check whether the implementation or the expected test result is
  wrong before changing the code; 24 is not a prime number.
- After the code block, add 2-3 short lines explaining what it does (in the user's language).
- If given an error, fix the code and return the full corrected code block."""

FENCE = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)


def _extract(text: str):
    m = FENCE.search(text)
    if not m:
        return None, None
    return (m.group(1) or "").lower(), m.group(2).strip()


def run(task: str, context: str = "", history=None) -> str:
    prompt = task if not context else f"Context:\n{context}\n\nTask:\n{task}"
    reply = chat(CODING_MODEL, SYSTEM, prompt, temperature=0.2, history=history)
    lang, code = _extract(reply)

    # Python nahi hai ya code nahi mila -> bas jawab wapas do
    if code is None or lang not in ("python", "py"):
        return reply

    log = []
    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        ok, output = run_python(code)
        if ok:
            log.append(f"Run #{attempt}: OK")
            result = f"{reply}\n\n---\n**Test run ({' -> '.join(log)}):**\n```\n{output or '(koi output nahi)'}\n```"
            return result
        log.append(f"Run #{attempt}: error")
        fix_prompt = f"Task:\n{task}\n\nYe code chalaya:\n```python\n{code}\n```\n\nError aaya:\n{output}\n\nCode fix karo."
        reply = chat(CODING_MODEL, SYSTEM, fix_prompt, temperature=0.2, history=history)
        lang, new_code = _extract(reply)
        if new_code is None:
            break
        code = new_code

    return f"{reply}\n\n---\n**Warning:** {MAX_FIX_ATTEMPTS} koshish ke baad bhi code theek se nahi chala. Last error:\n```\n{output}\n```"
