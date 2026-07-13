"""Build Agent / Prospect dialogue transcripts from Whisper segments."""

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
    "alpique",
    "engie",
    "edf",
    "total",
)

AGENT_MARKERS = (
    "je vous appelle",
    "je vous appellais",
    "je me présente",
    "société",
    "ogini",
    "eugénie",
    "eugenie",
    "origini",
    "comparateur",
    "fournisseur",
    "facture",
    "kilowatt",
    "kwh",
    "kiloateur",
    "contrat",
    "prélèvement",
    "prelevement",
    "confirmez",
    "récapitul",
    "recapitul",
    "madame,",
    "monsieur,",
    "sachez que",
    "l'appel est enregistré",
    "code de",
    "référence iban",
    "reference iban",
    "service client",
    "homénurgie",
    "homenurgie",
    "enménurgie",
    "enmenurgie",
    "on me ",
    "on va ",
    "je vais vous",
    "je vous propose",
    "je vous informe",
    "je vous rappelle",
    "montrez-moi",
    "dites-moi",
    "est-ce que vous",
    "vous me confirmez",
    "avant de continuer",
)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def classify_line(text: str, previous_role: str | None) -> str:
    lowered = text.lower().strip()
    word_count = len(text.split())

    if any(marker in lowered for marker in AGENT_MARKERS):
        return "agent"

    if re.search(r"\b(madame|monsieur)\b", lowered) and word_count <= 4:
        if lowered in {"oui.", "oui", "non.", "non", "bonjour.", "bonjour"}:
            return "prospect"
        return "agent"

    if lowered.startswith(("vous ", "est-ce ", "confirmez", "je vous", "je vais", "alors ", "voilà monsieur", "voilà madame")):
        return "agent"

    if word_count <= 8 and any(lowered.startswith(prefix) for prefix in CUSTOMER_STARTERS):
        return "prospect"

    if word_count <= 3 and not "?" in text:
        return "prospect"

    if "?" in text and word_count >= 5:
        return "agent"

    if word_count <= 12 and not any(ch.isdigit() for ch in text[:3]):
        if previous_role == "agent":
            return "prospect"
        if previous_role == "prospect":
            return "agent"

    if previous_role == "prospect":
        return "agent"
    if previous_role == "agent":
        return "prospect"
    return "agent"


def build_turns(segments: list[dict[str, object]]) -> list[dict[str, str | float]]:
    turns: list[dict[str, str | float]] = []
    previous_role: str | None = None

    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))

        for sentence in split_sentences(text):
            role = classify_line(sentence, previous_role)
            if turns and turns[-1]["role"] == role:
                turns[-1]["text"] = f"{turns[-1]['text']} {sentence}".strip()
                turns[-1]["end"] = end
            else:
                turns.append({"role": role, "text": sentence, "start": start, "end": end})
            previous_role = role

    return turns


def format_txt(turns: list[dict[str, str | float]], title: str) -> str:
    lines = [title, "=" * len(title), ""]
    for index, turn in enumerate(turns, start=1):
        label = "Agent" if turn["role"] == "agent" else "Prospect"
        start = turn.get("start", 0)
        lines.append(f"[{index:03d}] ({start:7.1f}s) {label}: {turn['text']}")
    return "\n".join(lines) + "\n"


def process_transcript(json_path: Path) -> tuple[Path, Path]:
    with json_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    segments = payload.get("segments", [])
    turns = build_turns(segments)

    output = {
        "source_audio": payload.get("audio_file", ""),
        "duration": payload.get("duration"),
        "turn_count": len(turns),
        "turns": turns,
    }

    dialogue_json = json_path.with_name(json_path.stem + "_dialogue.json")
    dialogue_txt = json_path.with_name(json_path.stem + "_dialogue.txt")

    with dialogue_json.open("w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)

    title = f"Dialogue — {json_path.stem}"
    dialogue_txt.write_text(format_txt(turns, title), encoding="utf-8")
    return dialogue_json, dialogue_txt


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "data" / "call_transcripts"
    for json_path in sorted(root.glob("*.json")):
        if json_path.name.endswith("_dialogue.json"):
            continue
        dialogue_json, dialogue_txt = process_transcript(json_path)
        print(f"{dialogue_json.name}: {dialogue_txt.name}")


if __name__ == "__main__":
    main()
