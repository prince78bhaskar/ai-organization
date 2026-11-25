"""Research Agent: search -> pages padho -> sources ke basis par report."""
from config import RESEARCH_MODEL
from llm import chat
from tools.web_search import fetch_page, search

QUERY_SYSTEM = "Convert the user's request into ONE short English web search query (max 8 words). Output only the query."

SYSTEM = """You are the Research Agent of an AI Organization.
You are given numbered web sources. Write a short, accurate report using ONLY those sources.
Rules:
- Reply in the user's language.
- Structure: Summary, Key Points (bullets), Sources.
- Cite sources as [1], [2] after each claim.
- If sources disagree or are weak, say so. Never invent facts or links."""


def run(task: str, context: str = "", history=None) -> str:
    query = chat(
        RESEARCH_MODEL, QUERY_SYSTEM, task, temperature=0.0, history=history
    ).strip().strip('"')
    queries = list(dict.fromkeys(q for q in (query, task) if q))
    errors = []
    results = []
    for candidate in queries:
        try:
            results = search(candidate, max_results=5)
        except Exception as e:
            errors.append(f"{candidate!r}: {e}")
        if results:
            break
    if not results:
        if errors:
            return "Web search fail hui: " + "; ".join(errors)
        return "Search mein koi result nahi mila."

    blocks = []
    for i, r in enumerate(results[:4], start=1):
        body = fetch_page(r["url"]) or r["snippet"]
        blocks.append(f"[{i}] {r['title']}\nURL: {r['url']}\n{body[:2500]}")
    sources_text = "\n\n".join(blocks)

    user = f"Request: {task}\n\nSources:\n{sources_text}"
    if context:
        user = f"Extra context:\n{context}\n\n" + user
    report = chat(RESEARCH_MODEL, SYSTEM, user, temperature=0.2, history=history)

    links = "\n".join(f"[{i}] {r['url']}" for i, r in enumerate(results[:4], start=1))
    return f"{report}\n\n**Links:**\n{links}"
