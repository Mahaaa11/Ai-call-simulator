#!/usr/bin/env python3
"""Transcribe a real call recording and save it for prospect-style training."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from engine.audio import live_call_transcriber, reference_call_transcriber
from engine.real_call_style import load_customer_lines_from_transcripts


def transcribe_recording(
    audio_path: Path,
    output_dir: Path,
    *,
    high_quality: bool = True,
    model_size: str | None = None,
) -> Path:
    """Transcribe audio and write JSON + TXT artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if model_size:
        from engine.audio import WhisperTranscriber

        transcriber = WhisperTranscriber(model_size=model_size, beam_size=5)
    elif high_quality:
        transcriber = reference_call_transcriber()
    else:
        transcriber = live_call_transcriber()

    result = transcriber.transcribe_detailed_file(audio_path)
    payload = {
        "audio_file": str(audio_path.resolve()),
        "model": result["model"],
        "language": result["language"],
        "language_probability": result["language_probability"],
        "duration": result["duration"],
        "text": result["text"],
        "segments": result["segments"],
    }

    stem = audio_path.stem
    json_path = output_dir / f"{stem}.json"
    txt_path = output_dir / f"{stem}.txt"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    txt_path.write_text(result["text"] + "\n", encoding="utf-8")

    customer_lines = load_customer_lines_from_transcripts(output_dir)
    print(f"Saved transcript ({result['model']}): {json_path}")
    print(f"Segments: {len(result['segments'])} | Prospect lines loaded: {len(customer_lines)}")
    return json_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a real sales call recording.")
    parser.add_argument("audio", type=Path, help="Path to wav/mp3/m4a recording")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "call_transcripts",
    )
    parser.add_argument("--model", default=None, help="Whisper model size override")
    parser.add_argument("--fast", action="store_true", help="Use faster lower-quality settings")
    args = parser.parse_args()

    if not args.audio.exists():
        raise SystemExit(f"Audio file not found: {args.audio}")

    transcribe_recording(
        args.audio,
        args.output_dir,
        high_quality=not args.fast,
        model_size=args.model,
    )


if __name__ == "__main__":
    main()
