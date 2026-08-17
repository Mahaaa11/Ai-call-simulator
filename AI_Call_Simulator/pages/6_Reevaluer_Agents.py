"""Réévaluer les dernières conversations d'agents avec la grille compliance v2."""

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

from mysql_store import (  # noqa: E402
    apply_mysql_env_from_mapping,
    find_latest_conversations_for_agents,
    list_recent_conversations_detailed,
    resolve_conversation_agent_name,
)
from reevaluate_agents import reevaluate_conversation  # noqa: E402


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


def _fmt_dt(value) -> str:
    if not value:
        return "—"
    return str(value)[:19]


st.set_page_config(page_title="Réévaluer agents", page_icon="🔄", layout="wide")
st.title("🔄 Réévaluer les dernières conversations")
st.caption(
    "Grille v2 : origine du numéro (jamais « base de données »), reformulation des objections, closing. "
    "Par défaut : **la dernière conversation** de chaque agent."
)

if not _mysql_from_secrets():
    st.error("MySQL/TiDB non configuré (Secrets Streamlit MYSQL_*).")
    st.stop()

default_agents = "Marc, Hassan, Mohamed Anas"
agents_raw = st.text_input("Agents (dernière conversation de chacun)", value=default_agents)
limit = st.number_input(
    "Conversations par agent",
    min_value=1,
    max_value=5,
    value=1,
    help="1 = uniquement la plus récente",
)
dry_run = st.checkbox("Simulation (ne pas écrire en base)", value=False)

targets = [a.strip() for a in agents_raw.split(",") if a.strip()]

# Aperçu avant lancement
try:
    preview = find_latest_conversations_for_agents(targets, per_agent=int(limit))
except Exception as exc:
    st.error(f"Impossible de lire TiDB : {exc}")
    st.stop()

st.subheader("Conversations qui seront réévaluées")
if not preview:
    st.warning(
        "Aucune conversation trouvée pour ces agents. "
        "Vérifiez les noms ou consultez le tableau des dernières conversations ci-dessous."
    )
else:
    preview_rows = []
    for row in preview:
        preview_rows.append({
            "ID": row["id"],
            "Agent (résolu)": row.get("_resolved_agent_name") or resolve_conversation_agent_name(row) or "—",
            "Date": _fmt_dt(row.get("created_at")),
            "Score actuel": row.get("score_total") if row.get("score_total") is not None else "—",
            "Profil": row.get("profile_key") or "—",
        })
    st.dataframe(preview_rows, use_container_width=True, hide_index=True)

with st.expander("Dernières conversations en base (diagnostic)"):
    try:
        recent = list_recent_conversations_detailed(limit=25)
        diag = []
        for row in recent:
            diag.append({
                "ID": row["id"],
                "Agent colonne": row.get("agent_name") or "—",
                "Agent résolu": resolve_conversation_agent_name(row) or "—",
                "Date": _fmt_dt(row.get("created_at")),
                "Score": row.get("score_total") if row.get("score_total") is not None else "—",
            })
        st.dataframe(diag, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.caption(f"Diagnostic indisponible : {exc}")

if st.button("Lancer la réévaluation", type="primary", disabled=not preview):
    with st.spinner("Réévaluation en cours…"):
        results = []
        for conv in preview:
            cid = int(conv["id"])
            agent = conv.get("_resolved_agent_name") or resolve_conversation_agent_name(conv)
            try:
                results.append(reevaluate_conversation(cid, dry_run=dry_run))
            except Exception as exc:
                results.append({"id": cid, "agent_name": agent, "error": str(exc)})

    st.session_state["reeval_results"] = results

if "reeval_results" in st.session_state:
    st.subheader("Résultats")
    for r in st.session_state["reeval_results"]:
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
        st.success(f"{len(st.session_state['reeval_results'])} conversation(s) réévaluée(s) en base TiDB.")
