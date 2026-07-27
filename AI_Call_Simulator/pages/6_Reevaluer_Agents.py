"""Réévaluer les conversations d'agents avec la grille compliance v2."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
ENV_PATH = PROJECT_ROOT / ".env"

for p in (WEB_DIR, SCRIPTS_DIR, PROJECT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from mysql_store import apply_mysql_env_from_mapping  # noqa: E402
from reevaluate_agents import find_conversations, reevaluate_conversation  # noqa: E402


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
    keys = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE", "MYSQL_SSL")
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


st.set_page_config(page_title="Réévaluer agents", page_icon="🔄", layout="wide")
st.title("🔄 Réévaluer les conversations")
st.caption(
    "Grille v2 : origine du numéro (jamais « base de données »), reformulation des objections, closing."
)

if not _mysql_from_secrets():
    st.error("MySQL/TiDB non configuré (Secrets Streamlit MYSQL_*).")
    st.stop()

default_agents = "Marc, Hassan, Mohamed Anas"
agents_raw = st.text_input("Agents à réévaluer", value=default_agents)
limit = st.number_input("Conversations max par recherche", min_value=1, max_value=10, value=3)
dry_run = st.checkbox("Simulation (ne pas écrire en base)", value=False)

targets = [a.strip() for a in agents_raw.split(",") if a.strip()]

if st.button("Lancer la réévaluation", type="primary"):
    try:
        convs = find_conversations(targets, limit_per_agent=int(limit))
    except Exception as exc:
        st.error(f"Erreur MySQL : {exc}")
        st.stop()

    if not convs:
        st.warning("Aucune conversation trouvée.")
        st.stop()

    results = []
    for conv in convs:
        cid = int(conv["id"])
        try:
            results.append(reevaluate_conversation(cid, dry_run=dry_run))
        except Exception as exc:
            results.append({"id": cid, "agent_name": conv.get("agent_name"), "error": str(exc)})

    for r in results:
        if r.get("error"):
            st.error(f"#{r['id']} — {r.get('agent_name')} : {r['error']}")
            continue
        comp = r.get("compliance") or {}
        old = r.get("old_score") or 0
        new = r.get("new_score") or 0
        delta = new - old
        sign = "+" if delta >= 0 else ""
        st.write(
            f"**#{r['id']}** — {r.get('agent_name')} : "
            f"{old} → **{new}** ({sign}{delta}) · {r.get('new_level')}"
        )
        if comp.get("bad_database_reply"):
            st.warning("⚠️ Mention « base de données » — pénalité appliquée.")
        elif comp.get("evasive_number_reply"):
            st.warning("⚠️ Réponse évasive sur l'origine du numéro.")
        st.caption(json.dumps(comp, ensure_ascii=False))

    if dry_run:
        st.info("Mode simulation — aucune modification en base.")
    else:
        st.success(f"{len(results)} conversation(s) réévaluée(s) en base TiDB.")
