"""Streamlit host for web/simulation.html with server-stored OpenRouter API key."""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SIMULATION_HTML = PROJECT_ROOT / "web" / "simulation.html"
ENV_PATH = PROJECT_ROOT / ".env"


def _load_env_file() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _get_openrouter_api_key() -> str:
    _load_env_file()
    try:
        secret = st.secrets.get("OPENROUTER_API_KEY", "")
        if secret:
            return str(secret).strip()
    except Exception:
        pass
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def _build_simulation_html(api_key: str) -> str:
    html = SIMULATION_HTML.read_text(encoding="utf-8")
    config = {
        "openrouterApiKey": api_key,
        "hostedOnStreamlit": True,
    }
    injection = (
        "<script>window.__SIMULATOR_CONFIG__ = "
        + json.dumps(config)
        + ";</script>"
    )
    if "</head>" in html:
        return html.replace("</head>", injection + "\n</head>", 1)
    return injection + html


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
            "- **Streamlit Cloud** : *Settings → Secrets*\n\n"
            "Exemple secrets :\n"
            "```toml\nOPENROUTER_API_KEY = \"sk-or-v1-...\"\n```"
        )
        st.stop()

    if not api_key.startswith("sk-or-"):
        st.warning("La clé OpenRouter devrait commencer par `sk-or-v1-...`")

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

    components.html(_build_simulation_html(api_key), height=1180, scrolling=True)
