#!/usr/bin/env python3
"""Build agent call structure examples from real call dialogue transcripts (v2)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS_DIR = ROOT / "data" / "call_transcripts"
OUT_JSON = ROOT / "data" / "agent_call_structure.json"
OUT_JS = ROOT / "web" / "assets" / "agent_call_structure.js"

PHASES: list[tuple[str, str, tuple[str, ...]]] = [
    (
        "opening",
        "Accroche — présentation + objet de l'appel",
        (
            "bonjour",
            "je vous appelle",
            "je vous appellais",
            "je me présente",
            "société",
            "ogini",
            "ogenies",
            "eugénie",
            "comparateur",
            "factures",
            "électricité",
            "c'est vous qui gérez",
            "gérez",
        ),
    ),
    (
        "discovery",
        "Découverte — fournisseur, facture, consommation",
        (
            "fournisseur",
            "payez combien",
            "par mois",
            "facture",
            "consommation",
            "kwh",
            "kilowatt",
            "gaz",
            "électricité seule",
            "tarif",
            "régularisation",
            "mensualité",
        ),
    ),
    (
        "comparatif",
        "Comparatif — gratuit, sans engagement, indépendant",
        (
            "comparatif",
            "comparateur",
            "sans engagement",
            "14 jours",
            "gratuit",
            "indépendant",
            "rétractation",
            "vérification",
            "5 minutes",
            "pas une vente",
        ),
    ),
    (
        "argumentation",
        "Argumentation — chiffres, économies, valeur",
        (
            "centimes",
            "kwh",
            "économ",
            "moins cher",
            "offre",
            "10%",
            "différence",
            "fournisseur",
            "même mode",
            "régularisation",
        ),
    ),
    (
        "closing",
        "Closing — coordonnées, IBAN, confirmation",
        (
            "iban",
            "prélèvement",
            "mandat",
            "confirmez",
            "adresse",
            "email",
            "e-mail",
            "date de naissance",
            "enregistrée",
            "autorisez",
            "code postal",
            "nom",
            "prénom",
        ),
    ),
    (
        "objection_handling",
        "Objections — empathie et relance",
        (
            "je comprends",
            "rassurez",
            "pas de souci",
            "d'accord",
            "parfait",
            "madame",
            "monsieur",
            "une seconde",
        ),
    ),
]

MIN_LEN = 25
MAX_LEN = 200


def is_low_quality(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\b[a-z](?:[-\s][a-z]){3,}", lowered):  # spelling letter by letter
        return True
    if text.count("?") >= 3:
        return True
    if len(text.split()) < 5:
        return True
    if re.search(r"(d'accord\.?\s*){3,}", lowered):
        return True
    if lowered in {"d'accord", "d'accord.", "une seconde", "parfait", "voilà"}:
        return True
    return False


def score_example(text: str, phase: str) -> int:
    lowered = text.lower()
    score = min(len(text.split()), 12)
    markers = next(m for pid, _, m in PHASES if pid == phase)
    score += sum(2 for m in markers if m in lowered)
    if phase == "opening" and ("je vous appelle" in lowered or "je me présente" in lowered):
        score += 5
    if phase == "discovery" and "?" in text:
        score += 2
    if phase == "comparatif" and "sans engagement" in lowered:
        score += 3
    if is_low_quality(text):
        score -= 20
    return score


def clean_line(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"(D'accord\.?\s*){2,}", "D'accord. ", text, flags=re.I)
    return text.strip(" .")


def classify_phase(text: str) -> str:
    lowered = text.lower()
    scores: dict[str, int] = {}
    for phase_id, _, markers in PHASES:
        scores[phase_id] = sum(1 for m in markers if m in lowered)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "discovery"
    return best


def load_dialogues() -> list[dict]:
    calls: list[dict] = []
    for path in sorted(TRANSCRIPTS_DIR.glob("*_dialogue.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        agent_turns = [
            clean_line(str(t.get("text", "")))
            for t in payload.get("turns", [])
            if t.get("role") == "agent"
        ]
        agent_turns = [t for t in agent_turns if len(t) >= MIN_LEN]
        calls.append({
            "id": path.stem.replace("_dialogue", ""),
            "source_audio": payload.get("source_audio", ""),
            "duration_sec": payload.get("duration"),
            "agent_turn_count": len(agent_turns),
            "agent_turns": agent_turns,
        })
    return calls


def pick_examples(calls: list[dict]) -> dict:
    by_phase: dict[str, list[str]] = {p[0]: [] for p in PHASES}
    seen: set[str] = set()

    for call in calls:
        scored: list[tuple[int, str]] = []
        for turn in call["agent_turns"]:
            if len(turn) > MAX_LEN or is_low_quality(turn):
                continue
            phase = classify_phase(turn)
            scored.append((score_example(turn, phase), turn))
        scored.sort(reverse=True)
        for _, turn in scored:
            key = turn.lower()[:80]
            if key in seen:
                continue
            phase = classify_phase(turn)
            if len(by_phase[phase]) >= 8:
                continue
            seen.add(key)
            by_phase[phase].append(turn)

    for phase_id, _, _ in PHASES:
        by_phase[phase_id].sort(key=lambda t: score_example(t, phase_id), reverse=True)
        by_phase[phase_id] = by_phase[phase_id][:6]

    opening_flows: list[dict] = []
    for call in calls:
        flow: list[str] = []
        for turn in call["agent_turns"][:12]:
            if len(turn) >= MIN_LEN and len(turn) <= MAX_LEN and not is_low_quality(turn):
                if "je vous appelle" in turn.lower() or "je me présente" in turn.lower() or "bonjour" in turn.lower():
                    flow.append(turn)
            if len(flow) >= 4:
                break
        if len(flow) >= 3:
            opening_flows.append({"call_id": call["id"], "sequence": flow})

    return {
        "phases": [
            {
                "id": phase_id,
                "label": label,
                "examples": by_phase[phase_id][:6],
            }
            for phase_id, label, _ in PHASES
        ],
        "opening_flows": opening_flows[:3],
    }


def build() -> dict:
    calls = load_dialogues()
    structure = pick_examples(calls)
    return {
        "source": "Transcriptions réelles ABDELLI, ADEMARD, AHMED (Whisper + dialogue split)",
        "calls": [
            {
                "id": c["id"],
                "duration_sec": c["duration_sec"],
                "agent_turn_count": c["agent_turn_count"],
            }
            for c in calls
        ],
        "structure": structure,
    }


def write_js(payload: dict) -> None:
    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text(
        "window.AGENT_CALL_STRUCTURE = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    payload = build()
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_js(payload)
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_JS}")
    for call in payload["calls"]:
        print(f"  - {call['id']}: {call['agent_turn_count']} agent turns")


if __name__ == "__main__":
    main()
