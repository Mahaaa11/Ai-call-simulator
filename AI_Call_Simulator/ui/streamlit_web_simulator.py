"""Streamlit host for web/simulation.html with server-stored OpenRouter API key."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from ui.conversation_bridge import conversation_bridge

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SIMULATION_HTML = PROJECT_ROOT / "web" / "simulation.html"
ENV_PATH = PROJECT_ROOT / ".env"
WEB_DIR = PROJECT_ROOT / "web"

if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from mysql_store import apply_mysql_env_from_mapping, check_mysql_connection, save_conversation


def _load_env_file() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _get_secret_or_env(name: str, default: str = "") -> str:
    _load_env_file()
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, default).strip()


def _mysql_secrets() -> dict[str, str]:
    keys = (
        "MYSQL_HOST",
        "MYSQL_PORT",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "MYSQL_DATABASE",
        "MYSQL_SSL",
    )
    return {key: _get_secret_or_env(key) for key in keys if _get_secret_or_env(key)}


def _configure_mysql_env() -> bool:
    values = _mysql_secrets()
    if not values.get("MYSQL_HOST"):
        return False
    apply_mysql_env_from_mapping(values)
    return True


def _get_openrouter_api_key() -> str:
    return _get_secret_or_env("OPENROUTER_API_KEY")


def _build_simulation_html(api_key: str, mysql_enabled: bool) -> str:
    html = SIMULATION_HTML.read_text(encoding="utf-8")
    config = {
        "openrouterApiKey": api_key,
        "hostedOnStreamlit": True,
    }
    api_url = _get_secret_or_env("CONVERSATION_API_URL")
    if api_url:
        config["conversationApiUrl"] = api_url
    elif mysql_enabled:
        config["streamlitSave"] = True
        config["mysqlEnabled"] = True
    save_feedback = st.session_state.pop("save_feedback", None)
    if save_feedback:
        config["lastSaveResult"] = save_feedback
    injection = (
        "<script>window.__SIMULATOR_CONFIG__ = "
        + json.dumps(config)
        + ";</script>"
    )
    if "</head>" in html:
        return html.replace("</head>", injection + "\n</head>", 1)
    return injection + html


def _payload_key(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _process_bridge_payload(payload: dict) -> None:
    key = _payload_key(payload)
    if st.session_state.get("last_save_key") == key:
        return
    try:
        conversation_id = save_conversation(payload)
        st.session_state.last_save_key = key
        st.session_state.save_feedback = {
            "ok": True,
            "conversation_id": conversation_id,
        }
    except Exception as exc:
        st.session_state.save_feedback = {
            "ok": False,
            "error": str(exc),
        }
    st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Simulateur d'appels IA",
        page_icon="📞",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    api_key = _get_openrouter_api_key()
    if not api_key:
        st.error("Clé OpenRouter manquante.")
        st.markdown(
            "Ajoutez `OPENROUTER_API_KEY` dans :\n"
            "- **Local** : fichier `.env` à la racine du projet\n"
            "- **Streamlit Cloud** : *Settings → Secrets*"
        )
        st.stop()

    mysql_enabled = _configure_mysql_env()
    mysql_ok = False
    mysql_detail = ""
    if mysql_enabled:
        mysql_ok, mysql_detail = check_mysql_connection()

    incoming = conversation_bridge(key="conversation_bridge")
    if incoming:
        _process_bridge_payload(incoming)

    st.markdown(
        """
        <style>
        header[data-testid="stHeader"] { background: transparent; }
        .block-container { padding-top: 0.5rem; padding-bottom: 0; max-width: 100%; }
        iframe { border: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if mysql_enabled and not mysql_ok:
        st.warning(f"MySQL configuré mais inaccessible : {mysql_detail}")

    components.html(_build_simulation_html(api_key, mysql_enabled and mysql_ok), height=1180, scrolling=True)
