"""Agent identification via Streamlit session (login by name)."""

from __future__ import annotations

import streamlit as st

SESSION_KEY = "logged_agent_name"


def get_agent_name() -> str:
    return str(st.session_state.get(SESSION_KEY) or "").strip()


def is_logged_in() -> bool:
    return len(get_agent_name()) >= 2


def login_agent(name: str) -> None:
    cleaned = " ".join(str(name or "").split())
    if len(cleaned) < 2:
        raise ValueError("Nom trop court")
    st.session_state[SESSION_KEY] = cleaned


def logout_agent() -> None:
    st.session_state.pop(SESSION_KEY, None)


def render_agent_banner() -> None:
    if not is_logged_in():
        return
    col1, col2 = st.columns([5, 1])
    with col1:
        st.success(f"Connecté : **{get_agent_name()}**")
    with col2:
        if st.button("Changer", key="agent_logout_btn"):
            logout_agent()
            st.rerun()


def render_login_form(*, compact: bool = False) -> None:
    title = "Identification agent" if compact else "👤 Identification agent"
    if not compact:
        st.title(title)
        st.caption(
            "Indiquez votre nom pour associer vos simulations "
            "et retrouver vos conversations dans l'historique."
        )
    else:
        st.subheader(title)

    with st.form("agent_login_form"):
        name = st.text_input(
            "Nom et prénom",
            placeholder="Ex : Alex Martin",
            autocomplete="name",
        )
        submit = st.form_submit_button("Entrer", type="primary", use_container_width=True)
        if submit:
            try:
                login_agent(name)
                st.rerun()
            except ValueError:
                st.error("Veuillez saisir au moins 2 caractères.")


def require_agent_login(*, compact: bool = False) -> None:
    """Stop the page until the agent identifies themselves."""
    if is_logged_in():
        render_agent_banner()
        return
    render_login_form(compact=compact)
    st.stop()
