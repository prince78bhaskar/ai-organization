"""Streamlit chat interface for the local AI Organization."""
import sys
import traceback
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import rag
from orchestrator import handle
from ui.components import (
    render_agent_cards,
    render_brand,
    render_chat_list,
    render_documents,
    render_welcome,
)
from ui.storage import (
    add_message,
    create_chat,
    delete_all_chats,
    delete_chat,
    load_store,
    save_store,
    sorted_chats,
)
from ui.styles import inject_styles


UPLOADS_DIR = ROOT / "uploads"
ALLOWED_TYPES = ["pdf", "png", "jpg", "txt", "md"]
HISTORY_CONTEXT_MESSAGES = 6

st.set_page_config(
    page_title="AI Organization",
    page_icon=":material/hub:",
    layout="wide",
)
inject_styles()

store, import_warning = load_store()
st.session_state.setdefault("active_chat_id", None)
st.session_state.setdefault("pending_delete_chat", None)
st.session_state.setdefault("pending_delete_all", False)
st.session_state.setdefault("queued_prompt", None)

chats = sorted_chats(store)
chat_ids = {chat["id"] for chat in chats}
if st.session_state.active_chat_id not in chat_ids:
    st.session_state.active_chat_id = None

with st.sidebar:
    render_brand()
    if st.button(
        "New chat",
        icon=":material/add:",
        type="primary",
        width="stretch",
        key="new_chat",
    ):
        chat = create_chat()
        store["chats"].append(chat)
        save_store(store)
        st.session_state.active_chat_id = chat["id"]
        st.session_state.pending_delete_chat = None
        st.rerun()

    st.markdown("**Chats**")
    action = render_chat_list(chats, st.session_state.active_chat_id)
    if action:
        action_name, chat_id = action
        if action_name == "select":
            st.session_state.active_chat_id = chat_id
            st.session_state.pending_delete_chat = None
            st.rerun()
        st.session_state.pending_delete_chat = chat_id
        st.rerun()

    pending_chat_id = st.session_state.pending_delete_chat
    pending_chat = next((chat for chat in chats if chat["id"] == pending_chat_id), None)
    if pending_chat:
        st.warning(f"Pakka delete? **{pending_chat['title']}**")
        confirm_column, cancel_column = st.columns(2)
        if confirm_column.button("Haan, delete", key="confirm_delete_chat"):
            delete_chat(store, pending_chat_id)
            save_store(store)
            if st.session_state.active_chat_id == pending_chat_id:
                remaining = sorted_chats(store)
                st.session_state.active_chat_id = remaining[0]["id"] if remaining else None
            st.session_state.pending_delete_chat = None
            st.rerun()
        if cancel_column.button("Nahi", key="cancel_delete_chat"):
            st.session_state.pending_delete_chat = None
            st.rerun()

    with st.expander("Delete all chats", expanded=st.session_state.pending_delete_all):
        if not st.session_state.pending_delete_all:
            if st.button("Delete all chats", key="request_delete_all", disabled=not chats):
                st.session_state.pending_delete_all = True
                st.rerun()
        else:
            st.warning("Pakka saari chats delete karni hain?")
            confirm_column, cancel_column = st.columns(2)
            if confirm_column.button("Haan, sab delete", key="confirm_delete_all"):
                delete_all_chats(store)
                save_store(store)
                st.session_state.active_chat_id = None
                st.session_state.pending_delete_chat = None
                st.session_state.pending_delete_all = False
                st.rerun()
            if cancel_column.button("Nahi", key="cancel_delete_all"):
                st.session_state.pending_delete_all = False
                st.rerun()

    try:
        documents = rag.list_documents()
    except Exception as error:
        documents = []
        st.warning("Ingested documents list load nahi ho saki.")
        with st.expander("Document list details"):
            st.code(str(error))
    render_documents(documents)
    show_steps = st.checkbox("Show agent steps", value=False, key="show_agent_steps")

if import_warning:
    st.warning(import_warning)

st.title("AI Organization")
st.caption("A local multi-agent workspace, powered by your configured Ollama models.")

agent_panel = st.empty()
with agent_panel.container():
    render_agent_cards()

active_chat = next(
    (chat for chat in store["chats"] if chat["id"] == st.session_state.active_chat_id),
    None,
)
if active_chat and active_chat["messages"]:
    for message in active_chat["messages"]:
        role = message["role"]
        avatar = ":material/person:" if role == "user" else ":material/smart_toy:"
        with st.chat_message(role, avatar=avatar):
            if message.get("error_details"):
                st.error(message["content"])
                with st.expander("Technical details"):
                    st.code(message["error_details"])
            else:
                st.markdown(message["content"])

            agents_used = message.get("agents_used", [])
            if role == "assistant" and agents_used:
                badges = " ".join(f":blue-badge[{name.title()}]" for name in agents_used)
                st.markdown(f"**Agents:** {badges}")

            steps = message.get("steps", [])
            events = message.get("events", [])
            if role == "assistant" and show_steps and (steps or events):
                with st.expander("Agent steps"):
                    for event in events:
                        st.caption(event)
                    for step in steps:
                        if isinstance(step, dict):
                            name, output = step.get("agent", "Agent"), step.get("output", "")
                        else:
                            name, output = step
                        st.markdown(f"**{name.title()} output**")
                        st.markdown(output)
elif not active_chat or not active_chat["messages"]:
    selected_prompt = render_welcome()
    if selected_prompt:
        st.session_state.queued_prompt = selected_prompt

if st.session_state.pop("clear_document_upload", False):
    st.session_state["document_upload"] = None

upload_column, ingest_column = st.columns([4, 1], vertical_alignment="bottom")
with upload_column:
    uploaded_files = st.file_uploader(
        "Add documents to RAG",
        type=ALLOWED_TYPES,
        accept_multiple_files=True,
        key="document_upload",
    )
with ingest_column:
    ingest_clicked = st.button(
        "Ingest files",
        icon=":material/upload_file:",
        disabled=not uploaded_files,
        width="stretch",
        key="ingest_uploaded_files",
    )

if ingest_clicked and uploaded_files:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for uploaded in uploaded_files:
        destination = UPLOADS_DIR / Path(uploaded.name).name
        try:
            destination.write_bytes(uploaded.getvalue())
            st.success(f"{uploaded.name}: {rag.ingest(str(destination))}")
        except Exception as error:
            st.error(f"{uploaded.name} ingest nahi ho saki.")
            with st.expander(f"Details: {uploaded.name}"):
                st.code(traceback.format_exc() or str(error))
    st.session_state["clear_document_upload"] = True

prompt = st.chat_input("Message AI Organization...")
if not prompt:
    prompt = st.session_state.pop("queued_prompt", None)

if prompt:
    if active_chat is None:
        active_chat = create_chat()
        store["chats"].append(active_chat)
        st.session_state.active_chat_id = active_chat["id"]

    user_message = {"role": "user", "content": prompt}
    add_message(active_chat, user_message)
    save_store(store)
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(prompt)

    events = []
    steps = []
    answer = ""
    error_details = None
    active_agents = []
    live_state = {"active_agent": "orchestrator"}
    with agent_panel.container():
        render_agent_cards(live_state["active_agent"])

    def report_step(event):
        events.append(event)
        if event.startswith("Agents:"):
            active_agents[:] = [
                name.strip()
                for name in event.partition(":")[2].split("->")
                if name.strip()
            ]
            live_state["active_agent"] = None
        elif event.startswith("[") and "]" in event:
            active_name = event[1:event.index("]")].strip().lower()
            live_state["active_agent"] = active_name
        with agent_panel.container():
            render_agent_cards(live_state["active_agent"])

    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        try:
            with st.status(":shimmer[Thinking...]", type="compact") as thinking:
                answer, steps = handle(
                    prompt,
                    on_step=report_step,
                    history=active_chat["messages"][:-1][-HISTORY_CONTEXT_MESSAGES:],
                )
                thinking.update(label="Response ready", state="complete")
        except Exception:
            error_details = traceback.format_exc()
            answer = "Sorry, I couldn't complete that request. Please check that Ollama is running and try again."
            st.error(answer)
            with st.expander("Technical details"):
                st.code(error_details)

        if error_details is None:
            failed_step = next(
                (
                    (name, output)
                    for name, output in steps
                    if output.startswith(f"{name} agent mein error:")
                ),
                None,
            )
            if failed_step:
                error_details = failed_step[1]
                answer = "Sorry, that agent ran into a problem while handling your request."
                st.error(answer)
                with st.expander("Technical details"):
                    st.code(error_details)
            else:
                st.markdown(answer)

        if active_agents:
            badges = " ".join(f":blue-badge[{name.title()}]" for name in active_agents)
            st.markdown(f"**Agents:** {badges}")
        if show_steps and (events or steps):
            with st.expander("Agent steps", expanded=True):
                for event in events:
                    st.caption(event)
                for name, output in steps:
                    st.markdown(f"**{name.title()} output**")
                    st.markdown(output)

    with agent_panel.container():
        render_agent_cards()

    assistant_message = {
        "role": "assistant",
        "content": answer,
        "agents_used": active_agents,
        "steps": [{"agent": name, "output": output} for name, output in steps],
        "events": events,
    }
    if error_details:
        assistant_message["error_details"] = error_details
    add_message(active_chat, assistant_message)
    save_store(store)
