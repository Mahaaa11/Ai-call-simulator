"""Historique des appels sauvegardés dans TiDB."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st

from ui.agent_session import get_agent_name, require_agent_login

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
ENV_PATH = PROJECT_ROOT / ".env"

for p in (WEB_DIR, SCRIPTS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from mysql_store import (
    apply_mysql_env_from_mapping,
    count_conversations,
    count_conversations_for_agent,
    get_conversation,
    get_conversation_messages,
    list_conversations,
    list_conversations_for_agent,
    resolve_conversation_agent_name,
)
from reevaluate_agents import reevaluate_conversation


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


def _fmt_dt(value) -> str:
    if not value:
        return "—"
    return str(value)[:19]


st.set_page_config(page_title="Historique des appels", page_icon="📋", layout="wide")
st.title("📋 Historique des conversations")
st.caption("Données lues depuis TiDB Cloud (base configurée dans Secrets Streamlit)")

require_agent_login(compact=True)
logged_agent = get_agent_name()

if not _mysql_from_secrets():
    st.error("MySQL non configuré. Ajoutez MYSQL_* dans les Secrets Streamlit.")
    st.stop()

db_name = os.getenv("MYSQL_DATABASE", "test")
st.info(f"Base active : **{db_name}**")

mine_only = st.toggle(
    f"Afficher uniquement mes conversations ({logged_agent})",
    value=True,
    help="Décochez pour voir toutes les conversations du centre.",
)

display_limit = st.number_input(
    "Nombre de conversations à afficher (plus récentes en premier)",
    min_value=10,
    max_value=500,
    value=100,
    step=10,
)

try:
    if mine_only:
        total = count_conversations_for_agent(logged_agent)
        rows = list_conversations_for_agent(logged_agent, limit=int(display_limit))
    else:
        total = count_conversations()
        rows = list_conversations(limit=int(display_limit))
except Exception as exc:
    st.error(f"Impossible de lire TiDB : {exc}")
    st.stop()

if total == 0:
    if mine_only:
        st.warning(
            f"Aucune conversation enregistrée pour **{logged_agent}**. "
            "Lancez une simulation depuis l'accueil — vos prochains appels apparaîtront ici."
        )
    else:
        st.warning("Aucune conversation enregistrée.")
    st.stop()

shown = len(rows)
scope = f" pour **{logged_agent}**" if mine_only else " (toutes)"
if shown >= total:
    st.success(f"**{total}** conversation(s){scope}")
else:
    st.success(
        f"**{total}** conversation(s){scope} — "
        f"**{shown}** plus récente(s) affichée(s)"
    )

agent_filter = st.text_input(
    "Affiner par nom (optionnel)",
    value="" if not mine_only else "",
    placeholder="Ex : Alex, Hamza",
).strip()

filtered_rows = rows
if agent_filter:
    needle = agent_filter.lower()
    filtered_rows = [
        r for r in rows
        if needle in str(resolve_conversation_agent_name(r) or r.get("agent_name") or "").lower()
    ]
    st.caption(f"{len(filtered_rows)} résultat(s) pour « {agent_filter} » sur les {shown} affichées")

table_rows = []
for r in filtered_rows:
    resolved = resolve_conversation_agent_name(r) or r.get("agent_name") or "—"
    table_rows.append({
        "ID": r["id"],
        "Agent": resolved,
        "Date": _fmt_dt(r.get("created_at")),
        "Profil": r.get("profile_key"),
        "Niveau": r.get("level_key"),
        "Mode": r.get("training_mode") or "train_agent",
        "Score": r.get("score_total") if r.get("score_total") is not None else "—",
        "Niveau éval": r.get("score_level") or "—",
    })

if not table_rows:
    st.warning("Aucune conversation ne correspond au filtre.")
    st.stop()

st.dataframe(table_rows, use_container_width=True, hide_index=True)

ids = [int(r["id"]) for r in filtered_rows]
default_id = ids[0]
selected = st.selectbox("Voir la transcription de l'appel", ids, index=0, format_func=lambda x: f"Conversation #{x}")

if not selected:
    st.stop()

conv = get_conversation(selected)
messages = get_conversation_messages(selected)

if not conv:
    st.error(f"Conversation #{selected} introuvable.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Score", conv.get("score_total") if conv.get("score_total") is not None else "—")
c2.metric("Agent", resolve_conversation_agent_name(conv) or conv.get("agent_name") or "—")
c3.metric("Profil", conv.get("profile_key") or "—")
c4.metric("Niveau", conv.get("level_key") or "—")
st.caption(f"Mode : {conv.get('training_mode') or 'train_agent'}")

reeval_key = f"reeval_done_{selected}"
if st.button("Réévaluer avec grille v2", type="secondary", key=f"reeval_btn_{selected}"):
    with st.spinner("Réévaluation en cours…"):
        try:
            result = reevaluate_conversation(selected, dry_run=False)
            st.session_state[reeval_key] = result
            conv = get_conversation(selected)
        except Exception as exc:
            st.error(f"Échec : {exc}")

if reeval_key in st.session_state:
    r = st.session_state[reeval_key]
    old = r.get("old_score") or 0
    new = r.get("new_score") or 0
    delta = new - old
    sign = "+" if delta >= 0 else ""
    st.success(f"Score mis à jour : {old} → **{new}** ({sign}{delta}) · {r.get('new_level')}")
    comp = r.get("compliance") or {}
    if comp.get("bad_database_reply"):
        st.warning("⚠️ Mention « base de données » détectée — pénalité appliquée.")
    elif comp.get("evasive_number_reply"):
        st.warning("⚠️ Réponse évasive sur l'origine du numéro.")

st.markdown(f"**Créée le :** {_fmt_dt(conv.get('created_at'))}")

st.subheader("Transcription")
for msg in messages:
    speaker = (msg.get("speaker") or "").lower()
    label = "Agent" if speaker == "agent" else "Prospect"
    color = "#eff6ff" if speaker == "agent" else "#f0fdf4"
    border = "#2563eb" if speaker == "agent" else "#16a34a"
    st.markdown(
        f'<div style="margin:8px 0;padding:12px;background:{color};'
        f'border-left:4px solid {border};border-radius:4px;">'
        f"<strong>{label} :</strong> {msg.get('content', '')}</div>",
        unsafe_allow_html=True,
    )

eval_raw = conv.get("evaluation_json")
if eval_raw:
    st.subheader("Évaluation")
    try:
        data = json.loads(eval_raw) if isinstance(eval_raw, str) else eval_raw
        if data.get("points_forts"):
            st.markdown("**Points forts**")
            for p in data["points_forts"]:
                st.markdown(f"- {p}")
        if data.get("axes_amelioration"):
            st.markdown("**Axes d'amélioration**")
            for p in data["axes_amelioration"]:
                st.markdown(f"- {p}")
        if data.get("commentaire"):
            st.markdown(f"*{data['commentaire']}*")
        with st.expander("JSON complet"):
            st.json(data)
    except json.JSONDecodeError:
        st.text(str(eval_raw))
