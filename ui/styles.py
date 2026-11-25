"""CSS polish for the Streamlit interface."""
import streamlit as st


CSS = """
<style>
[data-testid="stMainBlockContainer"] {
    max-width: 1080px;
    margin-inline: auto;
}
[data-testid="stSidebar"] {
    border-right: 1px solid rgba(128, 128, 128, 0.18);
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0.55rem;
}
button[kind="primary"], button[kind="secondary"] {
    border-radius: 0.8rem;
    transition: transform 120ms ease, box-shadow 120ms ease;
}
button[kind="primary"]:hover, button[kind="secondary"]:hover {
    transform: translateY(-1px);
}
.agent-card {
    min-height: 122px;
    padding: 0.8rem 0.9rem;
    border: 1px solid rgba(128, 128, 128, 0.24);
    border-radius: 14px;
    background: var(--secondary-background-color);
    transition: border-color 150ms ease, box-shadow 150ms ease;
}
.agent-card.working {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 1px var(--primary-color);
}
.agent-icon { font-size: 1.15rem; line-height: 1.4; }
.agent-name { font-weight: 650; margin-top: 0.2rem; }
.agent-description {
    min-height: 2.2rem;
    margin-top: 0.15rem;
    font-size: 0.78rem;
    opacity: 0.76;
}
.agent-model {
    overflow: hidden;
    margin-top: 0.25rem;
    font-size: 0.7rem;
    opacity: 0.66;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.agent-status {
    display: flex;
    align-items: center;
    gap: 0.38rem;
    margin-top: 0.45rem;
    font-size: 0.75rem;
}
.agent-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #8b949e;
}
.agent-card.working .agent-dot {
    background: var(--primary-color);
    animation: agent-pulse 1.15s ease-in-out infinite;
}
.orchestrator-card { margin-bottom: 0.65rem; }
.orchestrator-card .agent-card { min-height: auto; }
.agent-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.65rem;
}
.welcome-copy { padding: 2.2rem 0 1rem; text-align: center; }
.welcome-copy h1 { margin: 0.3rem 0; font-size: clamp(1.7rem, 3.5vw, 2.5rem); }
.welcome-copy p { margin: 0; opacity: 0.72; }
.welcome-eyebrow {
    color: var(--primary-color);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.12em;
}
[data-testid="stChatMessage"] {
    border-radius: 1rem;
}
pre {
    border-radius: 0.8rem !important;
}
#MainMenu, footer { visibility: hidden; }
@keyframes agent-pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(68, 120, 255, 0.35); }
    50% { opacity: 0.55; box-shadow: 0 0 0 5px rgba(68, 120, 255, 0); }
}
@media (max-width: 760px) {
    .agent-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .agent-card { min-height: 115px; padding: 0.65rem; }
    .welcome-copy { padding-top: 1.1rem; }
}
</style>
"""


def inject_styles():
    st.markdown(CSS, unsafe_allow_html=True)
