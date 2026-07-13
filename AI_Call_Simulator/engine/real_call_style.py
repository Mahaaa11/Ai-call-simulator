"""Load real call transcripts and extract prospect-style dialogue."""

from __future__ import annotations

import json
import re
from pathlib import Path


CUSTOMER_STARTERS = (
    "oui",
    "non",
    "d'accord",
    "alors",
    "euh",
    "je ",
    "moi ",
    "c'est ",
    "ah ",
    "bon ",
    "voilà",
    "merci",
    "ok",
)

AGENT_MARKERS = (
    "je vous appelle",
    "société",
    "madame,",
    "monsieur,",
    "je me présente",
    "comparateur",
    "fournisseur",
    "facture",
    "kilowatt",
    "kwh",
    "contrat",
    "prélèvement",
    "confirmez",
    "récapitul",
)


def load_customer_lines_from_transcripts(transcripts_dir: Path | str) -> list[str]:
    """Extract short prospect lines from saved call transcript JSON files."""
    directory = Path(transcripts_dir)
    if not directory.exists():
        return []

    lines: list[str] = []
    for path in sorted(directory.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (json.JSONDecodeError, OSError):
            continue

        segments = payload.get("segments")
        if isinstance(segments, list) and segments:
            lines.extend(_customer_lines_from_segments(segments))
            continue

        text = str(payload.get("text", "")).strip()
        if text:
            lines.extend(_customer_lines_from_text(text))

    return _dedupe_lines(lines)


def _customer_lines_from_segments(segments: list[dict[str, object]]) -> list[str]:
    extracted: list[str] = []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        for part in re.split(r"(?<=[.!?])\s+", text):
            clean = part.strip()
            if _looks_like_customer_line(clean):
                extracted.append(clean)
    return extracted


def _customer_lines_from_text(text: str) -> list[str]:
    extracted: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+", text):
        clean = part.strip()
        if _looks_like_customer_line(clean):
            extracted.append(clean)
    return extracted


def _looks_like_customer_line(text: str) -> bool:
    if len(text) < 2 or len(text) > 120:
        return False

    lowered = text.lower()
    word_count = len(text.split())
    if any(marker in lowered for marker in AGENT_MARKERS):
        return False

    if lowered.startswith(("vous ", "madame ", "monsieur ", "est-ce ", "confirmez", "je vous", "je vais")):
        return False

    if re.search(r"\b(madame|monsieur)\b", lowered) and word_count <= 4:
        return False

    if "?" in text and word_count > 6:
        return False

    if word_count <= 10:
        return True

    if word_count <= 16 and any(lowered.startswith(prefix) for prefix in CUSTOMER_STARTERS):
        return True

    return False


def _dedupe_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for line in lines:
        key = re.sub(r"\s+", " ", line.lower()).strip(" .!?")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(line)
    return unique


def format_customer_style_examples(lines: list[str], limit: int = 6, offset: int = 0) -> str:
    """Format real prospect lines for the system prompt."""
    if not lines:
        return "No real-call prospect examples loaded."

    start = max(0, offset % max(len(lines) - limit, 1))
    sample = lines[start : start + limit]
    formatted = [f"{index}. {line}" for index, line in enumerate(sample, start=1)]
    return (
        "Real prospect replies from recorded calls — match this tone:\n"
        + "\n".join(formatted)
    )
