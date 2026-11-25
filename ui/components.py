"""Reusable Streamlit UI components."""
from html import escape
from datetime import datetime

import streamlit as st

from config import (
    CODING_MODEL,
    EMBED_MODEL,
    ORCHESTRATOR_MODEL,
    RESEARCH_MODEL,
    STUDY_MODEL,
    VISION_MODEL,
)


AGENTS = [
    ("coding", "Coding", "⌨", "Writes and debugs code", CODING_MODEL),
    ("research", "Research", "⌕", "Finds and verifies information", RESEARCH_MODEL),
    ("study", "Study", "▤", "Explains topics and creates quizzes", STUDY_MODEL),
    (
        "rag",
        "RAG",
        "▣",
        "Answers from your documents",
        f"{STUDY_MODEL} / {VISION_MODEL} · {EMBED_MODEL}",
    ),
]


def render_brand():
    st.markdown("### :material/hub: AI Organization")
    st.caption("Your local team of AI agents")


def _agent_card(name, icon, description, model, state):
    working = state == "working"
    status_text = "Working..." if working else "Idle"
    status_class = "working" if working else "idle"
    return (
        f'<div class="agent-card {status_class}">'
        f'<div class="agent-icon">{escape(icon)}</div>'
        f'<div class="agent-name">{escape(name)}</div>'
        f'<div class="agent-description">{escape(description)}</div>'
        f'<div class="agent-model">{escape(model)}</div>'
        f'<div class="agent-status"><span class="agent-dot"></span>{status_text}</div>'
        "</div>"
    )


def render_agent_cards(active_agent=None):
    orchestrator_state = "working" if active_agent == "orchestrator" else "idle"
    orchestrator = _agent_card(
        "Master Orchestrator",
        "✦",
        "Plans the task and routes it to specialists",
        ORCHESTRATOR_MODEL,
        orchestrator_state,
    )
    cards = []
    for key, name, icon, description, model in AGENTS:
        state = "working" if active_agent == key else "idle"
        cards.append(_agent_card(name, icon, description, model, state))

    st.markdown(
        f'<div class="orchestrator-card">{orchestrator}</div>'
        f'<div class="agent-grid">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def _format_timestamp(value):
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%b %d · %I:%M %p")
    except (TypeError, ValueError):
        return "Date unavailable"


def render_chat_list(chats, active_id):
    for chat in chats:
        first_column, second_column = st.columns([5, 1], vertical_alignment="center")
        with first_column:
            if st.button(
                chat["title"] or "New chat",
                key=f"select_chat_{chat['id']}",
                type="primary" if chat["id"] == active_id else "secondary",
                width="stretch",
            ):
                return ("select", chat["id"])
            st.caption(_format_timestamp(chat.get("updated_at")))
        with second_column:
            if st.button(
                "Delete",
                key=f"delete_chat_{chat['id']}",
                icon=":material/delete:",
                help=f"Delete {chat['title']}",
            ):
                return ("delete", chat["id"])
    return None


def render_welcome():
    st.markdown(
        '<div class="welcome-copy"><div class="welcome-eyebrow">AI ORGANIZATION</div>'
        "<h1>What can I help you with?</h1>"
        "<p>Choose an agent to get started, or ask your own question below.</p></div>",
        unsafe_allow_html=True,
    )
    suggestions = [
        ("Coding", ":material/code:", "Write a Python function to check if a number is prime, with tests."),
        ("Research", ":material/travel_explore:", "Research AI agents and summarize the most important ideas."),
        ("Study", ":material/school:", "Explain recursion simply and create a short quiz."),
        ("RAG", ":material/folder_open:", "Answer a question using my uploaded documents."),
    ]
    selected_prompt = None
    first_row = st.columns(2)
    second_row = st.columns(2)
    for index, (name, icon, prompt) in enumerate(suggestions):
        column = first_row[index] if index < 2 else second_row[index - 2]
        with column:
            with st.container(border=True):
                st.markdown(f"**{icon} {name}**")
                st.caption(prompt)
                if st.button(
                    f"Use {name.lower()} prompt",
                    key=f"suggestion_{name.lower()}",
                    width="stretch",
                ):
                    selected_prompt = prompt
    return selected_prompt


def render_documents(documents):
    label = f"Ingested documents ({len(documents)})"
    with st.expander(label, expanded=False):
        if documents:
            for document in documents:
                st.markdown(f"- `{document}`")
        else:
            st.caption("No documents ingested yet.")
