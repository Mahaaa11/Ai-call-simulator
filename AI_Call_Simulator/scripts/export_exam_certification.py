#!/usr/bin/env python3
"""Export exam certifications: agents, transcripts and evaluations to Excel."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from mysql_store import (  # noqa: E402
    get_conversation_messages,
    list_exam_certified_conversations,
)

DEFAULT_DATE = "2026-07-17"
DEFAULT_MIN_SCORE = 70
OUT_DIR = PROJECT_ROOT / "data" / "exports"


def _load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        import os

        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _resolve_agent_name(row: dict) -> str:
    name = (row.get("agent_name") or "").strip()
    if name:
        return name
    raw = row.get("evaluation_json")
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            meta = data.get("exam_meta") or {}
            name = (meta.get("agent_name") or "").strip()
            if name:
                return name
        except (json.JSONDecodeError, TypeError):
            pass
    return f"Agent #{row.get('id')}"


def _parse_evaluation(row: dict) -> dict:
    raw = row.get("evaluation_json")
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def build_export_rows(
    *,
    exam_date: str | None,
    min_score: int,
) -> tuple[list[dict], list[dict], list[dict]]:
    rows = list_exam_certified_conversations(min_score=min_score, exam_date=exam_date)
    summary: list[dict] = []
    transcripts: list[dict] = []
    evaluations: list[dict] = []

    best_by_agent: dict[str, dict] = {}
    for row in rows:
        agent = _resolve_agent_name(row)
        key = agent.lower()
        if key not in best_by_agent:
            best_by_agent[key] = row

    for row in sorted(best_by_agent.values(), key=lambda r: (-int(r.get("score_total") or 0), r.get("id") or 0)):
        agent = _resolve_agent_name(row)
        conv_id = int(row["id"])
        score = row.get("score_total")
        created = row.get("created_at")
        created_str = str(created)[:19] if created else ""
        eval_data = _parse_evaluation(row)
        summary.append({
            "Agent": agent,
            "Score": score,
            "Niveau": row.get("score_level") or eval_data.get("niveau") or "",
            "Certifié": "Oui" if (score or 0) >= min_score else "Non",
            "Date appel": created_str,
            "Conversation ID": conv_id,
            "Profil": row.get("profile_key") or "",
            "Mode": row.get("training_mode") or "",
        })

        for msg in get_conversation_messages(conv_id):
            speaker = msg.get("speaker") or ""
            label = "Agent" if speaker == "agent" else "Prospect"
            transcripts.append({
                "Agent": agent,
                "Conversation ID": conv_id,
                "Ordre": msg.get("seq"),
                "Interlocuteur": label,
                "Message": msg.get("content") or "",
            })

        points_forts = eval_data.get("points_forts") or []
        axes = eval_data.get("axes_amelioration") or []
        reco = eval_data.get("recommandations") or []
        section_lines = []
        for sec in eval_data.get("sections") or []:
            section_lines.append(f"{sec.get('name')} : {sec.get('score')}/{sec.get('max')}")
            for item in sec.get("items") or []:
                section_lines.append(f"  - {item.get('name')} ({item.get('score')}/{item.get('max')}) : {item.get('comment')}")

        evaluations.append({
            "Agent": agent,
            "Conversation ID": conv_id,
            "Score total": score,
            "Niveau": eval_data.get("niveau") or row.get("score_level") or "",
            "Points forts": "\n".join(f"• {p}" for p in points_forts),
            "Axes amélioration": "\n".join(f"• {a}" for a in axes),
            "Recommandations": "\n".join(f"• {r}" for r in reco),
            "Détail grille": "\n".join(section_lines),
        })

    summary.sort(key=lambda r: (-int(r["Score"] or 0), r["Agent"]))
    return summary, transcripts, evaluations


def export_excel(
    output_path: Path,
    *,
    exam_date: str | None = DEFAULT_DATE,
    min_score: int = DEFAULT_MIN_SCORE,
) -> int:
    import pandas as pd

    summary, transcripts, evaluations = build_export_rows(
        exam_date=exam_date,
        min_score=min_score,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(summary or [{"Info": "Aucun agent certifié pour le moment"}]).to_excel(
            writer, sheet_name="Agents certifiés", index=False
        )
        pd.DataFrame(transcripts or [{"Info": "—"}]).to_excel(
            writer, sheet_name="Transcriptions", index=False
        )
        pd.DataFrame(evaluations or [{"Info": "—"}]).to_excel(
            writer, sheet_name="Évaluations", index=False
        )

    return len(summary)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export exam certification results to Excel")
    parser.add_argument("--date", default=DEFAULT_DATE, help="Exam date YYYY-MM-DD (empty = all dates)")
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE, help="Minimum score")
    parser.add_argument(
        "--output",
        default="",
        help="Output .xlsx path (default: data/exports/examen_certification_<date>.xlsx)",
    )
    args = parser.parse_args()
    _load_env()

    exam_date = args.date.strip() or None
    suffix = exam_date or "all"
    output = Path(args.output) if args.output else OUT_DIR / f"examen_certification_{suffix}.xlsx"

    count = export_excel(output, exam_date=exam_date, min_score=args.min_score)
    print(f"Exporté {count} agent(s) certifié(s) → {output}")


if __name__ == "__main__":
    main()
