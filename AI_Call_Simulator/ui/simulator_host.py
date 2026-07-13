"""Shared Streamlit host for simulation HTML pages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import streamlit as st

from ui.simulator_component import simulator_frame

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
WEB_DIR = PROJECT_ROOT / "web"

if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from mysql_store import (
    apply_mysql_env_from_mapping,
    check_mysql_connection,
    save_conversation,
    update_conversation_evaluation,
)


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


def _is_local_api_url(url: str) -> bool:
    lower = url.lower()
    return any(token in lower for token in ("127.0.0.1", "localhost", "0.0.0.0"))


def _inject_config(html: str, config: dict) -> str:
    injection = (
        "<script>window.__SIMULATOR_CONFIG__ = "
        + json.dumps(config, ensure_ascii=False)
        + ";</script>"
    )
    cleaned = re.sub(
        r"<script>window\.__SIMULATOR_CONFIG__\s*=\s*[\s\S]*?;</script>\s*",
        "",
        html,
    )
    if "</head>" in cleaned:
        return cleaned.replace("</head>", injection + "\n</head>", 1)
    return injection + cleaned


def _build_html_content(html_path: Path, config: dict) -> str:
    embed_config = {k: v for k, v in config.items() if k != "lastSaveResult"}
    html = html_path.read_text(encoding="utf-8")
    return _inject_config(html, embed_config)


def _content_key(html_path: Path, config: dict) -> str:
    payload = {
        "page": html_path.name,
        "mysql": bool(config.get("mysqlEnabled")),
        "api": bool(config.get("openrouterApiKey")),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _build_streamlit_config(
    api_key: str,
    mysql_configured: bool,
    mysql_ok: bool,
    extra_config: dict | None = None,
) -> dict:
    config: dict = {
        "openrouterApiKey": api_key,
        "hostedOnStreamlit": True,
        "streamlitSave": True,
    }
    if extra_config:
        config.update(extra_config)
    api_url = _get_secret_or_env("CONVERSATION_API_URL")

    if mysql_configured:
        config["mysqlEnabled"] = True
        if not mysql_ok:
            config["mysqlConnectionWarning"] = True
    elif api_url and not _is_local_api_url(api_url):
        config["conversationApiUrl"] = api_url.rstrip("/")
        config["streamlitSave"] = False

    save_feedback = st.session_state.pop("save_feedback", None)
    if save_feedback:
        config["lastSaveResult"] = save_feedback
    return config


def _payload_key(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _process_bridge_payload(payload: dict) -> bool:
    key = _payload_key(payload)
    if st.session_state.get("last_save_key") == key:
        return False
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
    return True


def _process_eval_update(incoming: dict) -> bool:
    conversation_id = int(incoming.get("conversation_id") or 0)
    evaluation = incoming.get("evaluation") or {}
    if not conversation_id:
        return False
    key = _payload_key({"conversation_id": conversation_id, "evaluation": evaluation})
    update_key = f"eval:{key}"
    if st.session_state.get("last_save_key") == update_key:
        return False
    try:
        update_conversation_evaluation(conversation_id, evaluation)
        st.session_state.last_save_key = update_key
        st.session_state.save_feedback = {
            "ok": True,
            "conversation_id": conversation_id,
            "updated": True,
        }
    except Exception as exc:
        st.session_state.save_feedback = {
            "ok": False,
            "error": str(exc),
            "conversation_id": conversation_id,
        }
    return True


def _handle_incoming(incoming: dict | object) -> bool:
    if not incoming:
        return False
    if isinstance(incoming, dict) and incoming.get("action") == "update_eval":
        return _process_eval_update(incoming)
    if isinstance(incoming, dict) and incoming.get("action") == "save":
        return _process_bridge_payload(incoming.get("payload") or {})
    if isinstance(incoming, dict):
        return _process_bridge_payload(incoming)
    return False


def _render_status_bar(api_key: str, mysql_enabled: bool, mysql_ok: bool, mysql_detail: str) -> None:
    c1, c2 = st.columns(2)
    with c1:
        if api_key:
            st.success("Clé OpenRouter : configurée (Secrets)")
        else:
            st.error("Clé OpenRouter : manquante")
    with c2:
        if mysql_enabled and mysql_ok:
            st.success("MySQL : connecté (sauvegarde directe Streamlit)")
        elif mysql_enabled:
            st.warning(f"MySQL : {mysql_detail}")
        else:
            st.info("MySQL : ajoutez MYSQL_* dans Secrets Streamlit")


def run_simulator(
    html_path: Path,
    *,
    page_title: str,
    page_icon: str = "📞",
    iframe_height: int = 1180,
    extra_config: dict | None = None,
) -> None:
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
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
        if st.session_state.get("mysql_ok") is None:
            ok, detail = check_mysql_connection()
            st.session_state.mysql_ok = ok
            st.session_state.mysql_detail = detail
        mysql_ok = bool(st.session_state.mysql_ok)
        mysql_detail = str(st.session_state.mysql_detail or "")

    config = _build_streamlit_config(api_key, mysql_enabled, mysql_ok, extra_config)
    html_content = _build_html_content(html_path, config)
    content_key = _content_key(html_path, config)

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

    _render_status_bar(api_key, mysql_enabled, mysql_ok, mysql_detail)

    incoming = simulator_frame(
        html_content=html_content,
        config=config,
        content_key=content_key,
        height=iframe_height,
        key="simulator_frame",
    )
    if incoming and _handle_incoming(incoming):
        st.rerun()
