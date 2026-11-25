"""Ollama ke upar ek chhota wrapper. Saare agents isi ko use karte hain."""
import re
import ollama


def _clean(text: str) -> str:
    # Kuch models <think>...</think> likhte hain, use hata do
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def chat(model, system, user, images=None, as_json=False, temperature=0.3, history=None):
    """Ek baar model se baat karo aur text wapas lo.

    images: list of file paths (sirf vision model ke liye)
    as_json: True ho to model ko JSON output dene par majboor karta hai
    """
    messages = [{"role": "system", "content": system}]
    if history:
        messages += history
    msg = {"role": "user", "content": user}
    if images:
        msg["images"] = images
    messages.append(msg)

    kwargs = dict(model=model, messages=messages, options={"temperature": temperature})
    if as_json:
        kwargs["format"] = "json"

    try:
        # think=False: thinking models fast jawab dein (chhote laptop par zaroori)
        resp = ollama.chat(think=False, **kwargs)
    except (TypeError, ollama.ResponseError):
        resp = ollama.chat(**kwargs)
    return _clean(resp["message"]["content"])


def embed(model, texts):
    """Text ki list ko vectors mein badlo (RAG ke liye)."""
    resp = ollama.embed(model=model, input=texts)
    return resp["embeddings"]
