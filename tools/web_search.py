"""Internet search + page text nikalna."""


def search(query: str, max_results: int = 5):
    """DuckDuckGo se results lao: [{'title','url','snippet'}, ...]"""
    try:
        try:
            from ddgs import DDGS  # naya package naam
        except ImportError:
            from duckduckgo_search import DDGS  # purana naam
    except ImportError:
        raise RuntimeError("Web search ke liye install karo: pip install ddgs")

    results = []
    with DDGS() as d:
        for r in d.text(query, max_results=max_results):
            results.append(
                {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            )
    return results


def fetch_page(url: str, max_chars: int = 3500) -> str:
    """Page ka saaf text lao. Fail ho to khali string."""
    try:
        import trafilatura
    except ImportError:
        return ""
    try:
        html = trafilatura.fetch_url(url)
        if not html:
            return ""
        text = trafilatura.extract(html) or ""
        return text[:max_chars]
    except Exception:
        return ""
