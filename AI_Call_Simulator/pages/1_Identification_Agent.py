"""Identification agent — associer un nom aux simulations."""

from __future__ import annotations

import os
import sys
from html import escape
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
from ui.brand_theme import inject_global_css, render_feature_cards, render_hero, safe_page_config  # noqa: E402


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


safe_page_config(page_title="Identification agent", page_icon="👤", layout="wide")
inject_global_css()
render_hero(
    "Espace agent",
    "Identifiez-vous pour lancer une simulation et enregistrer vos performances.",
    badge="Lead & Connect · Training",
)

if is_logged_in():
    name = get_agent_name()
    safe_name = escape(name)
    st.markdown(
        f"""
        <div class="lc-card" style="border-left:4px solid #00827F;">
          <h3>✅ Connecté · {safe_name}</h3>
          <p>Votre nom sera associé à chaque appel simulé et à votre évaluation.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if _mysql_from_secrets():
        try:
            total = count_conversations_for_agent(name)
            st.markdown(
                f"""
                <div class="lc-grid">
                  <div class="lc-stat"><div class="num">{total}</div><div class="lbl">Conversations enregistrées</div></div>
                  <div class="lc-stat"><div class="num">2</div><div class="lbl">Modes disponibles</div></div>
                  <div class="lc-stat"><div class="num">70+</div><div class="lbl">Score certification</div></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        except Exception as exc:
            st.warning(f"Impossible de lire TiDB : {exc}")

    st.markdown("#### Choisissez votre simulation")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
            <div class="lc-card">
              <h3>📞 Mode 1 : vous êtes l'agent</h3>
              <p>Vous vendez — l'IA joue le prospect Engie avec objections RGPD.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("pages/_mode1_agent.py", label="Lancer Mode 1 →", icon="📞")
    with c2:
        st.markdown(
            """
            <div class="lc-card">
              <h3>🎭 Mode 2 : vous êtes le prospect</h3>
              <p>Vous jouez le client — l'IA agent doit traiter vos objections.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("pages/2_Mode_Prospect_IA.py", label="Lancer Mode 2 →", icon="🎭")

    if st.button("Se déconnecter / changer de nom"):
        logout_agent()
        st.rerun()
else:
    render_feature_cards()
    st.markdown('<div class="lc-card">', unsafe_allow_html=True)
    render_login_form()
    st.markdown("</div>", unsafe_allow_html=True)
    st.caption("Après identification, vos appels seront enregistrés avec votre nom.")
