#!/usr/bin/env python3
"""Generate one PDF per agent from evaluationAgents.docx."""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

DOCX_PATH = Path("/Users/macbookpro/Desktop/evaluationAgents.docx")
OUT_DIR = Path("/Users/macbookpro/Desktop/evaluations_agents")

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def para_text(p: ET.Element) -> str:
    parts: list[str] = []
    for t in p.findall(".//w:t", NS):
        if t.text:
            parts.append(t.text)
        if t.tail:
            parts.append(t.tail)
    return "".join(parts).strip()


def load_paragraphs(docx_path: Path) -> list[str]:
    with zipfile.ZipFile(docx_path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)
    return [para_text(p) for p in body.findall("w:p", NS)]


def is_agent_header(text: str, next_text: str) -> bool:
    if not text or not next_text.startswith("Prospect"):
        return False
    if text.startswith(("Prospect", "Agent")):
        return False
    if len(text) > 30 or " " in text:
        return False
    return text.replace("-", "").replace("'", "").isalpha()


def split_sections(paras: list[str]) -> list[tuple[str, list[str]]]:
    starts: list[tuple[int, str]] = []
    for idx, text in enumerate(paras):
        nxt = paras[idx + 1].strip() if idx + 1 < len(paras) else ""
        if is_agent_header(text.strip(), nxt):
            starts.append((idx, text.strip()))

    sections: list[tuple[str, list[str]]] = []
    for i, (start_idx, name) in enumerate(starts):
        end_idx = starts[i + 1][0] if i + 1 < len(starts) else len(paras)
        content = [p for p in paras[start_idx:end_idx] if p.strip()]
        sections.append((name, content))
    return sections


def safe_filename(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", name, flags=re.UNICODE).strip("_")
    return slug or "agent"


def escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\xa0", " ")
    )


def classify_line(text: str) -> str:
    if text.startswith("Prospect"):
        return "prospect"
    if text.startswith("Agent"):
        return "agent"
    if text.startswith("Évaluation —") or text.startswith("Rapport"):
        return "eval_title"
    if "Score global" in text or re.match(r"^\d+/100", text.replace("\xa0", "")):
        return "score"
    if text in (
        "Détail par critère",
        "Détail",
        "3 points forts",
        "3 points forts de l'agent",
        "3 axes d'amélioration",
        "Recommandations",
        "Grille pédagogique /100 · Télévente énergie",
    ):
        return "section"
    if re.match(r"^\d+\.\s", text):
        return "criterion"
    return "body"


def build_pdf(name: str, lines: list[str], out_path: Path) -> None:
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Évaluation — {name}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AgentTitle",
        parent=styles["Heading1"],
        fontSize=20,
        spaceAfter=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#166534"),
    )
    eval_title_style = ParagraphStyle(
        "EvalTitle",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#181818"),
        backColor=colors.HexColor("#F3F4F6"),
    )
    score_style = ParagraphStyle(
        "Score",
        parent=styles["Heading3"],
        fontSize=13,
        spaceAfter=10,
        textColor=colors.HexColor("#B45309"),
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading4"],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#374151"),
    )
    prospect_style = ParagraphStyle(
        "Prospect",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        leftIndent=8,
        spaceBefore=4,
        spaceAfter=2,
        backColor=colors.HexColor("#ECFDF5"),
        borderPadding=6,
    )
    agent_style = ParagraphStyle(
        "AgentLine",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        leftIndent=8,
        spaceBefore=4,
        spaceAfter=2,
        backColor=colors.HexColor("#EFF6FF"),
        borderPadding=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceBefore=2,
        spaceAfter=2,
    )
    criterion_style = ParagraphStyle(
        "Criterion",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceBefore=4,
        spaceAfter=2,
        leftIndent=12,
        textColor=colors.HexColor("#1F2937"),
    )

    story = []
    story.append(Paragraph(escape_xml(name), title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 0.3 * cm))

    for line in lines[1:]:  # skip duplicate header name
        kind = classify_line(line)
        escaped = escape_xml(line)
        if kind == "prospect":
            story.append(Paragraph(f"<b>{escaped}</b>", prospect_style))
        elif kind == "agent":
            story.append(Paragraph(f"<b>{escaped}</b>", agent_style))
        elif kind == "eval_title":
            story.append(Spacer(1, 0.2 * cm))
            story.append(Paragraph(f"<b>{escaped}</b>", eval_title_style))
        elif kind == "score":
            story.append(Paragraph(f"<b>{escaped}</b>", score_style))
        elif kind == "section":
            story.append(Paragraph(f"<b>{escaped}</b>", section_style))
        elif kind == "criterion":
            story.append(Paragraph(escaped, criterion_style))
        else:
            story.append(Paragraph(escaped, body_style))

    doc.build(story)


def main() -> None:
    if not DOCX_PATH.exists():
        raise SystemExit(f"Fichier introuvable : {DOCX_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paras = load_paragraphs(DOCX_PATH)
    sections = split_sections(paras)

    if not sections:
        raise SystemExit("Aucune section agent détectée dans le document.")

    print(f"Agents détectés : {len(sections)}")
    for name, lines in sections:
        out_path = OUT_DIR / f"Evaluation_{safe_filename(name)}.pdf"
        build_pdf(name, lines, out_path)
        print(f"  ✓ {out_path.name} ({len(lines)} paragraphes)")

    print(f"\nPDFs générés dans : {OUT_DIR}")


if __name__ == "__main__":
    main()
