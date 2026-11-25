"""Study Agent: concepts samjhana, notes, quiz, exam prep."""
from config import STUDY_MODEL
from llm import chat

SYSTEM = """Tum ek dhairyawan Study Agent ho (AI Organization ka Study department).
Kaam: concepts simple bhasha mein samjhana, revision notes banana, quiz aur exam prep.
Rules:
- User jis bhasha mein likhe (Hindi/Hinglish/English), usi mein jawab do.
- Pehle simple samjhao, phir example do, phir short summary.
- Notes maango to bullet points + key terms do.
- Quiz maango to MCQ do aur end mein answers likho.
- Agar 'Context' diya gaya hai (kisi doosre agent ka kaam), use base banakar kaam karo.
- Jo nahi pata, uska andaza mat lagao; saaf batao."""


def run(task: str, context: str = "", history=None) -> str:
    user = task if not context else f"Context (doosre agent se):\n{context}\n\nTask:\n{task}"
    return chat(STUDY_MODEL, SYSTEM, user, temperature=0.4, history=history)
