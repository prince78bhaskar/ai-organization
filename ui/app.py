"""Streamlit chat interface for the local AI Organization."""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import rag
from memory.history import append_exchange, clear_history, load_history, save_history
from orchestrator import handle

UPLOADS_DIR = ROOT / "uploads"
ALLOWED_TYPES = ["pdf", "png", "jpg", "txt", "md"]

st.set_page_config(page_title="AI Organization", page_icon=":robot_face:")
st.title("AI Organization")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = load_history()

with st.sidebar:
    st.header("Documents")
    uploaded_files = st.file_uploader(
        "Upload files to the RAG agent",
        type=ALLOWED_TYPES,
        accept_multiple_files=True,
    )
    if st.button("Save and ingest files", disabled=not uploaded_files):
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        for uploaded in uploaded_files:
            destination = UPLOADS_DIR / Path(uploaded.name).name
            destination.write_bytes(uploaded.getvalue())
            st.write(f"{uploaded.name}: {rag.ingest(str(destination))}")

    documents = rag.list_documents()
    st.caption("Ingested documents")
    if documents:
        for document in documents:
            st.write(f"- {document}")
    else:
        st.caption("Abhi koi document ingest nahi hua.")

    show_steps = st.checkbox("Show agent steps", value=False)
    if st.button("New chat / Clear history"):
        clear_history()
        st.session_state.chat_history = []
        st.rerun()

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Apna sawaal likho...")
if prompt:
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    events = []
    with st.chat_message("assistant"):
        with st.spinner("Agents kaam kar rahe hain..."):
            answer, steps = handle(
                prompt,
                on_step=events.append,
                history=st.session_state.chat_history[:-1][-10:],
            )
        st.markdown(f"**Agents:** {' -> '.join(name for name, _ in steps)}")
        if show_steps:
            with st.expander("Agent steps"):
                for event in events:
                    st.write(event)
                for name, output in steps:
                    st.markdown(f"**{name} output**")
                    st.markdown(output)
        st.markdown(answer)

    st.session_state.chat_history = append_exchange(
        st.session_state.chat_history[:-1], prompt, answer
    )
    save_history(st.session_state.chat_history)
