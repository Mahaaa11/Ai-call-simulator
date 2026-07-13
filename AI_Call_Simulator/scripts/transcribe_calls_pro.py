#!/usr/bin/env python3
"""Transcribe reference calls with AssemblyAI (French + speaker diarization)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from engine.assemblyai_transcriber import ProTranscriptionError, save_transcription, transcribe_call


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcription pro AssemblyAI avec diarisation.")
    parser.add_argument(
        "audio",
        nargs="*",
        type=Path,
        help="Fichier(s) audio. Sans argument: tous les WAV dans data/reference_recordings/",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "call_transcripts",
    )
    args = parser.parse_args()

    if args.audio:
        files = args.audio
    else:
        files = sorted((PROJECT_ROOT / "data" / "reference_recordings").glob("*.wav"))

    if not files:
        raise SystemExit("Aucun fichier audio trouvé.")

    for index, audio_path in enumerate(files, start=1):
        if not audio_path.exists():
            print(f"Ignoré (introuvable): {audio_path}")
            continue
        print(f"\n[{index}/{len(files)}] Transcription pro: {audio_path.name}")
        try:
            payload = transcribe_call(audio_path)
            json_path, dialogue_path = save_transcription(payload, args.output_dir, audio_path.stem)
            print(f"  OK → {dialogue_path.name} ({len(payload['turns'])} tours)")
        except ProTranscriptionError as exc:
            print(f"  ERREUR: {exc}")
            if "Clé AssemblyAI manquante" in str(exc):
                raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
