"""Streamlit chat interface over the shared agent entrypoint."""

import asyncio

import streamlit as st

from src.agent.graph import run_agent
from src.agent.personas import PERSONAS, SECTORS

st.set_page_config(page_title="Financial Agent", page_icon="📊")
st.title("Persona-Configurable Financial Agent")
st.caption("Every factual answer is grounded in the configured MCP data source.")

persona = st.sidebar.selectbox(
    "Analyst persona",
    list(PERSONAS),
    format_func=lambda value: value.replace("_", " ").title(),
)
sector = st.sidebar.selectbox("Sector", list(SECTORS))

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ask a grounded financial question")
if prompt is not None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        response = asyncio.run(run_agent(prompt, persona, sector))
        st.markdown(response.answer)
        st.caption(f"Confidence: {response.confidence} · Persona: {response.persona}")
    st.session_state.messages.append({"role": "assistant", "content": response.answer})
