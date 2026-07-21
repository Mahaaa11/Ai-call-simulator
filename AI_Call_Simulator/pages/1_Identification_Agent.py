"""Identification agent — associer un nom aux simulations."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
ENV_PATH = PROJECT_ROOT / ".env"

if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from mysql_store import apply_mysql_env_from_mapping, count_conversations_for_agent  # noqa: E402
from ui.agent_session import (  # noqa: E402
    get_agent_name,
    is_logged_in,
    logout_agent,
    render_login_form,
)


def _load_env() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _mysql_from_secrets() -> bool:
    _load_env()
    keys = (
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_DATABASE",
        "MYSQL_SSL",
    )
    values = {}
    for key in keys:
        try:
            val = st.secrets.get(key, "")
        except Exception:
            val = ""
        if not val:
            val = os.getenv(key, "")
        if val:
            values[key] = str(val).strip()
    if not values.get("MYSQL_HOST"):
        return False
    apply_mysql_env_from_mapping(values)
    return True


st.set_page_config(page_title="Identification agent", page_icon="👤", layout="centered")
st.title("👤 Espace agent")

if is_logged_in():
    name = get_agent_name()
    st.success(f"Vous êtes connecté en tant que **{name}**")

    if _mysql_from_secrets():
        try:
            total = count_conversations_for_agent(name)
            st.metric("Vos conversations enregistrées", total)
        except Exception as exc:
            st.warning(f"Impossible de lire TiDB : {exc}")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.page_link("app.py", label="📞 Lancer une simulation", icon="📞")
    with c2:
        st.page_link("pages/3_Historique_Appels.py", label="📋 Mes conversations", icon="📋")
    if st.button("Se déconnecter / changer de nom"):
        logout_agent()
        st.rerun()
else:
    render_login_form()
    st.caption("Après identification, vos appels seront enregistrés avec votre nom.")
