"""Historique des appels sauvegardés dans TiDB."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
ENV_PATH = PROJECT_ROOT / ".env"

if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from mysql_store import (
    apply_mysql_env_from_mapping,
    get_conversation,
    get_conversation_messages,
    list_conversations,
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


def _fmt_dt(value) -> str:
    if not value:
        return "—"
    return str(value)[:19]


st.set_page_config(page_title="Historique des appels", page_icon="📋", layout="wide")
st.title("📋 Historique des conversations")
st.caption("Données lues depuis TiDB Cloud (base configurée dans Secrets Streamlit)")

if not _mysql_from_secrets():
    st.error("MySQL non configuré. Ajoutez MYSQL_* dans les Secrets Streamlit.")
    st.stop()

db_name = os.getenv("MYSQL_DATABASE", "test")
st.info(f"Base active : **{db_name}**")

try:
    rows = list_conversations(limit=100)
except Exception as exc:
    st.error(f"Impossible de lire TiDB : {exc}")
    st.stop()

if not rows:
    st.warning("Aucune conversation enregistrée.")
    st.stop()

st.success(f"**{len(rows)}** conversation(s) trouvée(s)")

table_rows = []
for r in rows:
    table_rows.append({
        "ID": r["id"],
        "Date": _fmt_dt(r.get("created_at")),
        "Profil": r.get("profile_key"),
        "Niveau": r.get("level_key"),
        "Mode": r.get("training_mode") or "train_agent",
        "Score": r.get("score_total") if r.get("score_total") is not None else "—",
        "Niveau éval": r.get("score_level") or "—",
    })

st.dataframe(table_rows, use_container_width=True, hide_index=True)

ids = [int(r["id"]) for r in rows]
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
c2.metric("Profil", conv.get("profile_key") or "—")
c3.metric("Niveau", conv.get("level_key") or "—")
c4.metric("Mode", conv.get("training_mode") or "train_agent")

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
