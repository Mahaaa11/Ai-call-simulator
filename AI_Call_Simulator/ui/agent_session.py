"""Agent identification via Streamlit session (login by name)."""

from __future__ import annotations

import streamlit as st

SESSION_KEY = "logged_agent_name"
HISTORY_UNLOCK_KEY = "history_admin_unlocked"
DEFAULT_HISTORY_ACCESS_CODE = "2003"


def get_history_access_code() -> str:
    try:
        code = st.secrets.get("HISTORY_ACCESS_CODE", "")
    except Exception:
        code = ""
    return str(code or DEFAULT_HISTORY_ACCESS_CODE).strip()


def is_history_unlocked() -> bool:
    return bool(st.session_state.get(HISTORY_UNLOCK_KEY))


def unlock_history(code: str) -> bool:
    if str(code or "").strip() == get_history_access_code():
        st.session_state[HISTORY_UNLOCK_KEY] = True
        return True
    return False


def lock_history() -> None:
    st.session_state.pop(HISTORY_UNLOCK_KEY, None)


def require_history_access() -> None:
    """Stop the page until the admin access code is entered."""
    if is_history_unlocked():
        col1, col2 = st.columns([5, 1])
        with col1:
            st.caption("Accès administration déverrouillé.")
        with col2:
            if st.button("Verrouiller", key="history_lock_btn"):
                lock_history()
                st.rerun()
        return

    st.title("🔒 Accès restreint")
    st.caption("Cette section est réservée à l'administration.")
    with st.form("history_access_form"):
        code = st.text_input(
            "Code d'accès",
            type="password",
            placeholder="Code administrateur",
            autocomplete="off",
        )
        submit = st.form_submit_button("Déverrouiller", type="primary", use_container_width=True)
        if submit:
            if unlock_history(code):
                st.rerun()
            st.error("Code incorrect.")
    st.stop()


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
            "Indiquez votre nom pour associer vos simulations à votre profil agent."
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
