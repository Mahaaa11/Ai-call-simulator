#!/usr/bin/env python3
"""Evaluate a pasted transcript and export PDF (grille v2)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from evaluation_engine import compute_heuristic_evaluation  # noqa: E402

from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer


def escape_xml(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\xa0", " ")
    )


def parse_transcript(text: str) -> list[dict]:
    messages: list[dict] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(Prospect|Agent)\s*:\s*(.+)$", line, re.I)
        if not m:
            continue
        speaker = "prospect" if m.group(1).lower() == "prospect" else "agent"
        messages.append({"speaker": speaker, "content": m.group(2).strip()})
    return messages


def format_grid_detail(evaluation: dict) -> str:
    lines: list[str] = []
    for section in evaluation.get("sections") or []:
        lines.append(f"{section['name']} — {section['score']}/{section['max']}")
        for item in section.get("items") or []:
            lines.append(f"  • {item['name']} : {item['score']}/{item['max']} — {item.get('comment', '—')}")
    return "\n".join(lines)


def build_pdf(
    agent_name: str,
    messages: list[dict],
    evaluation: dict,
    out_path: Path,
    *,
    exam_date: str = "27 juillet 2026",
    prospect_label: str = "Marc Dupont (Engie)",
) -> None:
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Évaluation — {agent_name}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#002D58"),
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#666666"),
        spaceAfter=12,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=14,
        spaceAfter=8,
        textColor=colors.HexColor("#002D58"),
    )
    score_style = ParagraphStyle(
        "Score",
        parent=styles["Heading3"],
        fontSize=12,
        spaceAfter=8,
        textColor=colors.HexColor("#B45309"),
    )
    prospect_style = ParagraphStyle(
        "Prospect",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        leftIndent=6,
        spaceBefore=3,
        spaceAfter=2,
        backColor=colors.HexColor("#ECFDF5"),
        borderPadding=5,
    )
    agent_style = ParagraphStyle(
        "AgentLine",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        leftIndent=6,
        spaceBefore=3,
        spaceAfter=2,
        backColor=colors.HexColor("#EFF6FF"),
        borderPadding=5,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        spaceBefore=2,
        spaceAfter=2,
    )
    detail_style = ParagraphStyle(
        "Detail",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        leftIndent=10,
        spaceBefore=1,
        spaceAfter=1,
        textColor=colors.HexColor("#374151"),
    )
    alert_style = ParagraphStyle(
        "Alert",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        spaceBefore=4,
        spaceAfter=4,
        textColor=colors.HexColor("#B91C1C"),
        backColor=colors.HexColor("#FEF2F2"),
        borderPadding=6,
    )

    score = evaluation.get("score_total", 0)
    niveau = evaluation.get("niveau", "")
    certifie = "Oui" if score >= 70 else "Non"
    compliance = evaluation.get("_compliance") or {}

    story = []
    story.append(Paragraph(escape_xml(agent_name), title_style))
    story.append(
        Paragraph(
            escape_xml(f"Examen certification Engie — {exam_date} · Prospect : {prospect_label}"),
            subtitle_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("<b>Transcription de l'appel</b>", section_style))
    for msg in messages:
        label = "Agent" if msg["speaker"] == "agent" else "Prospect"
        style = agent_style if label == "Agent" else prospect_style
        story.append(Paragraph(f"<b>{label} :</b> {escape_xml(msg['content'])}", style))

    story.append(Paragraph("<b>Évaluation (grille v2)</b>", section_style))
    story.append(
        Paragraph(
            escape_xml(f"Score : {score}/100 · {niveau} · Certifié : {certifie}"),
            score_style,
        )
    )

    if compliance.get("bad_database_reply"):
        story.append(
            Paragraph(
                "<b>Alerte compliance :</b> l'agent a mentionné une « base de contact / base de données » "
                "lorsque le prospect a demandé l'origine de son numéro — pénalité majeure appliquée (-18 pts).",
                alert_style,
            )
        )
    elif compliance.get("ignored_number_reply"):
        story.append(
            Paragraph(
                "<b>Alerte compliance :</b> le prospect a demandé l'origine de son numéro et l'agent "
                "a enchaîné sur un autre sujet sans répondre — pénalité appliquée (-10 pts).",
                alert_style,
            )
        )

    for section_title, key in (
        ("Points forts", "points_forts"),
        ("Axes d'amélioration", "axes_amelioration"),
        ("Recommandations", "recommandations"),
    ):
        items = evaluation.get(key) or []
        if items:
            story.append(Paragraph(f"<b>{section_title}</b>", body_style))
            for item in items:
                story.append(Paragraph(f"• {escape_xml(item)}", body_style))

    story.append(Paragraph("<b>Détail par critère</b>", body_style))
    for line in format_grid_detail(evaluation).split("\n"):
        if line.strip():
            style = detail_style if line.startswith("  •") else body_style
            story.append(Paragraph(escape_xml(line), style))

    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="Mohamed Anas")
    parser.add_argument("--input", type=Path, help="Transcript file (Prospect:/Agent: lines)")
    parser.add_argument("--output", type=Path, default="")
    args = parser.parse_args()

    if args.input:
        text = args.input.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    messages = parse_transcript(text)
    if not messages:
        print("Aucun message parsé.", file=sys.stderr)
        return 1

    evaluation = compute_heuristic_evaluation(messages)
    out = args.output.expanduser() if args.output else (
        PROJECT_ROOT / "data" / "exports" / f"Evaluation_{args.agent.replace(' ', '_')}.pdf"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    build_pdf(args.agent, messages, evaluation, out)
    print(f"PDF généré : {out}")
    print(f"Score : {evaluation['score_total']}/100 — {evaluation['niveau']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
