"""Professional call transcription with AssemblyAI speaker diarization."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProTranscriptionError(RuntimeError):
    """Raised when professional transcription cannot be completed."""


AGENT_MARKERS = (
    "je vous appelle",
    "je vous appellais",
    "je me présente",
    "société",
    "ogini",
    "eugénie",
    "comparateur",
    "fournisseur",
    "facture",
    "kilowatt",
    "kwh",
    "contrat",
    "prélèvement",
    "confirmez",
    "récapitul",
    "service client",
    "homénurgie",
    "homenurgie",
    "enménurgie",
    "code de",
    "référence iban",
    "sachez que",
    "l'appel est enregistré",
    "est-ce que vous",
    "vous me confirmez",
    "madame,",
    "monsieur,",
)


@dataclass(frozen=True)
class DialogueTurn:
    role: str
    text: str
    start: float
    end: float
    speaker: str


def get_api_key() -> str:
    key = os.environ.get("ASSEMBLYAI_API_KEY", "").strip()
    if not key:
        raise ProTranscriptionError(
            "Clé AssemblyAI manquante. Créez un compte gratuit sur https://www.assemblyai.com "
            "puis exportez ASSEMBLYAI_API_KEY=votre_cle"
        )
    return key


def transcribe_agent_bytes(audio_bytes: bytes, suffix: str = ".wav") -> str:
    """Transcribe a short agent microphone clip in French (no diarization)."""
    if not audio_bytes:
        raise ProTranscriptionError("Le fichier audio est vide.")

    try:
        import assemblyai as aai
    except ImportError as exc:
        raise ProTranscriptionError("Installez AssemblyAI: pip install assemblyai") from exc

    aai.settings.api_key = get_api_key()
    config = aai.TranscriptionConfig(language_code="fr")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temp_file:
        temp_file.write(audio_bytes)
        temp_file.flush()
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(temp_file.name)

    if transcript.status == aai.TranscriptStatus.error:
        raise ProTranscriptionError(transcript.error or "Transcription AssemblyAI échouée.")

    text = (transcript.text or "").strip()
    if not text:
        raise ProTranscriptionError("Aucune parole détectée dans l'enregistrement.")
    return text


def transcribe_call(audio_path: Path) -> dict[str, Any]:
    """Transcribe a call with French language and speaker diarization."""
    try:
        import assemblyai as aai
    except ImportError as exc:
        raise ProTranscriptionError(
            "Installez AssemblyAI: pip install assemblyai"
        ) from exc

    aai.settings.api_key = get_api_key()
    config = aai.TranscriptionConfig(
        language_code="fr",
        speaker_labels=True,
        speakers_expected=2,
    )
    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(str(audio_path))

    if transcript.status == aai.TranscriptStatus.error:
        raise ProTranscriptionError(transcript.error or "Transcription AssemblyAI échouée.")

    utterances = transcript.utterances or []
    if not utterances:
        raise ProTranscriptionError("Aucune réplique détectée dans l'audio.")

    agent_speaker = _identify_agent_speaker(utterances)
    turns = _build_turns(utterances, agent_speaker)
    segments = [
        {
            "start": round(turn.start, 2),
            "end": round(turn.end, 2),
            "text": turn.text,
            "speaker": turn.speaker,
            "role": turn.role,
        }
        for turn in turns
    ]

    return {
        "audio_file": str(audio_path.resolve()),
        "provider": "assemblyai",
        "language": "fr",
        "duration": round(float(getattr(transcript, "audio_duration", 0) or 0), 2),
        "text": " ".join(turn.text for turn in turns).strip(),
        "agent_speaker": agent_speaker,
        "segments": segments,
        "turns": [
            {"role": turn.role, "text": turn.text, "start": turn.start, "end": turn.end}
            for turn in turns
        ],
    }


def _identify_agent_speaker(utterances: list[Any]) -> str:
    scores: dict[str, int] = defaultdict(int)
    for index, utterance in enumerate(utterances[:40]):
        text = utterance.text.strip()
        lowered = text.lower()
        speaker = utterance.speaker

        for marker in AGENT_MARKERS:
            if marker in lowered:
                scores[speaker] += 3

        if "?" in text and len(text.split()) >= 5:
            scores[speaker] += 2

        if len(text.split()) <= 4:
            scores[speaker] -= 1

        if index < 3 and any(marker in lowered for marker in ("société", "je vous appelle", "comparateur")):
            scores[speaker] += 4

    if not scores:
        return utterances[0].speaker
    return max(scores, key=scores.get)


def _build_turns(utterances: list[Any], agent_speaker: str) -> list[DialogueTurn]:
    turns: list[DialogueTurn] = []
    for utterance in utterances:
        text = re.sub(r"\s+", " ", utterance.text.strip())
        if not text:
            continue
        role = "agent" if utterance.speaker == agent_speaker else "prospect"
        start = float(utterance.start) / 1000.0
        end = float(utterance.end) / 1000.0

        if turns and turns[-1].role == role:
            turns[-1] = DialogueTurn(
                role=role,
                text=f"{turns[-1].text} {text}".strip(),
                start=turns[-1].start,
                end=end,
                speaker=utterance.speaker,
            )
        else:
            turns.append(
                DialogueTurn(
                    role=role,
                    text=text,
                    start=start,
                    end=end,
                    speaker=utterance.speaker,
                )
            )
    return turns


def format_dialogue_txt(turns: list[dict[str, Any]], title: str) -> str:
    lines = [title, "=" * len(title), ""]
    for index, turn in enumerate(turns, start=1):
        label = "Agent" if turn["role"] == "agent" else "Prospect"
        start = float(turn.get("start", 0))
        lines.append(f"[{index:03d}] ({start:7.1f}s) {label}: {turn['text']}")
    return "\n".join(lines) + "\n"


def save_transcription(payload: dict[str, Any], output_dir: Path, stem: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    txt_path = output_dir / f"{stem}.txt"
    dialogue_json = output_dir / f"{stem}_dialogue.json"
    dialogue_txt = output_dir / f"{stem}_dialogue.txt"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    txt_path.write_text(payload["text"] + "\n", encoding="utf-8")

    dialogue_payload = {
        "source_audio": payload.get("audio_file"),
        "provider": payload.get("provider"),
        "turn_count": len(payload["turns"]),
        "agent_speaker": payload.get("agent_speaker"),
        "turns": payload["turns"],
    }
    with dialogue_json.open("w", encoding="utf-8") as file:
        json.dump(dialogue_payload, file, ensure_ascii=False, indent=2)

    title = f"Dialogue pro — {stem}"
    dialogue_txt.write_text(format_dialogue_txt(payload["turns"], title), encoding="utf-8")
    return json_path, dialogue_txt
