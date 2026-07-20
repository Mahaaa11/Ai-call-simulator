#!/usr/bin/env python3
"""Generate one PDF per agent from exam certification Excel export."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer


def safe_filename(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")
    return slug or "agent"


def escape_xml(text: str) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\xa0", " ")
    )


def bullet_lines(text: str) -> list[str]:
    if not text or (isinstance(text, float) and pd.isna(text)):
        return []
    lines = []
    for raw in str(text).split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("•"):
            line = line[1:].strip()
        lines.append(line)
    return lines


def build_agent_pdf(
    agent_name: str,
    meta: dict,
    transcript_rows: list[dict],
    evaluation: dict,
    out_path: Path,
) -> None:
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Examen — {agent_name}",
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

    story = []
    story.append(Paragraph(escape_xml(agent_name), title_style))
    story.append(
        Paragraph(
            escape_xml(
                f"Examen certification — 17 juillet 2026 · Conversation #{meta.get('Conversation ID', '')}"
            ),
            subtitle_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 0.25 * cm))

    story.append(Paragraph("<b>Transcription de l'appel</b>", section_style))
    for row in transcript_rows:
        speaker = row.get("Interlocuteur") or ""
        msg = row.get("Message") or ""
        label = "Agent" if speaker == "Agent" else "Prospect"
        style = agent_style if label == "Agent" else prospect_style
        story.append(Paragraph(f"<b>{label} :</b> {escape_xml(msg)}", style))

    story.append(Paragraph("<b>Évaluation</b>", section_style))
    score = evaluation.get("Score total", meta.get("Score", ""))
    niveau = evaluation.get("Niveau", meta.get("Niveau", ""))
    certifie = meta.get("Certifié", "")
    story.append(
        Paragraph(
            escape_xml(f"Score : {score}/100 · {niveau} · Certifié : {certifie}"),
            score_style,
        )
    )

    for section_title, key in (
        ("Points forts", "Points forts"),
        ("Axes d'amélioration", "Axes amélioration"),
        ("Recommandations", "Recommandations"),
    ):
        items = bullet_lines(evaluation.get(key, ""))
        if items:
            story.append(Paragraph(f"<b>{section_title}</b>", body_style))
            for item in items:
                story.append(Paragraph(f"• {escape_xml(item)}", body_style))

    detail = evaluation.get("Détail grille", "")
    if detail and not (isinstance(detail, float) and pd.isna(detail)):
        story.append(Paragraph("<b>Détail par critère</b>", body_style))
        for line in str(detail).split("\n"):
            line = line.strip()
            if line:
                story.append(Paragraph(escape_xml(line), detail_style))

    doc.build(story)


def export_pdfs_from_excel(xlsx_path: Path, out_dir: Path) -> list[Path]:
    agents_df = pd.read_excel(xlsx_path, sheet_name="Agents certifiés")
    transcripts_df = pd.read_excel(xlsx_path, sheet_name="Transcriptions")
    evaluations_df = pd.read_excel(xlsx_path, sheet_name="Évaluations")

    out_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    for _, agent_row in agents_df.iterrows():
        agent_name = str(agent_row["Agent"]).strip()
        conv_id = agent_row["Conversation ID"]

        transcript_rows = (
            transcripts_df[transcripts_df["Conversation ID"] == conv_id]
            .sort_values("Ordre")
            .to_dict("records")
        )

        eval_rows = evaluations_df[evaluations_df["Conversation ID"] == conv_id]
        evaluation = eval_rows.iloc[0].to_dict() if not eval_rows.empty else {}

        out_path = out_dir / f"Examen_{safe_filename(agent_name)}.pdf"
        build_agent_pdf(agent_name, agent_row.to_dict(), transcript_rows, evaluation, out_path)
        created.append(out_path)

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate exam PDFs from Excel export")
    parser.add_argument(
        "xlsx",
        nargs="?",
        default="/Users/macbookpro/Downloads/examen_certification_2026-07-17.xlsx",
        help="Path to exam certification Excel file",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory (default: <xlsx_dir>/examen_pdfs_2026-07-17)",
    )
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx).expanduser().resolve()
    if not xlsx_path.exists():
        raise SystemExit(f"Fichier introuvable : {xlsx_path}")

    out_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else xlsx_path.parent / "examen_pdfs_2026-07-17"
    )

    paths = export_pdfs_from_excel(xlsx_path, out_dir)
    print(f"Généré {len(paths)} PDF(s) dans {out_dir}")
    for p in paths:
        print(f"  - {p.name}")


if __name__ == "__main__":
    main()
