"""Export Excel — agents certifiés à l'examen du jour."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import streamlit as st

from ui.agent_session import require_admin_access

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
ENV_PATH = PROJECT_ROOT / ".env"

if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mysql_store import apply_mysql_env_from_mapping  # noqa: E402
from scripts.export_exam_certification import (  # noqa: E402
    DEFAULT_MIN_SCORE,
    build_export_rows,
    export_excel,
)


from ui.brand_theme import safe_page_config  # noqa: E402


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


safe_page_config(page_title="Export examen certification", page_icon="📊", layout="wide")
require_admin_access()
st.title("📊 Export examen certification")
st.caption("Archive — examen du 17/07/2026 terminé. Export des agents certifiés (score ≥ 70/100).")

if not _mysql_from_secrets():
    st.error("MySQL non configuré. Ajoutez MYSQL_* dans les Secrets Streamlit.")
    st.stop()

exam_date = st.date_input("Date de l'examen", value=date(2026, 7, 17))
min_score = st.number_input("Score minimum", min_value=0, max_value=100, value=DEFAULT_MIN_SCORE)
date_str = exam_date.isoformat()

try:
    summary, transcripts, evaluations = build_export_rows(
        exam_date=date_str,
        min_score=int(min_score),
    )
except Exception as exc:
    st.error(f"Impossible de lire la base : {exc}")
    st.stop()

st.success(f"**{len(summary)}** agent(s) certifié(s) trouvé(s) pour le {date_str}")

if summary:
    st.dataframe(summary, use_container_width=True, hide_index=True)

    out_path = PROJECT_ROOT / "data" / "exports" / f"examen_certification_{date_str}.xlsx"
    export_excel(out_path, exam_date=date_str, min_score=int(min_score))

    with open(out_path, "rb") as f:
        xlsx_bytes = f.read()

    st.download_button(
        label="⬇️ Télécharger le fichier Excel complet",
        data=xlsx_bytes,
        file_name=f"examen_certification_{date_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    with st.expander("Aperçu transcriptions"):
        st.dataframe(transcripts[:200], use_container_width=True, hide_index=True)

    with st.expander("Aperçu évaluations"):
        st.dataframe(evaluations, use_container_width=True, hide_index=True)
else:
    st.info(
        "Aucun agent certifié pour l'instant. "
        "Les agents doivent saisir leur nom dans le panneau examen avant de passer l'appel."
    )
