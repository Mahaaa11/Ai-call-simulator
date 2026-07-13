#!/usr/bin/env python3
"""Re-transcribe all reference call recordings with high-quality Whisper settings."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RECORDINGS_DIR = PROJECT_ROOT / "data" / "reference_recordings"
TRANSCRIPTS_DIR = PROJECT_ROOT / "data" / "call_transcripts"


def main() -> None:
    recordings = sorted(RECORDINGS_DIR.glob("*.wav"))
    if not recordings:
        raise SystemExit(f"No WAV files found in {RECORDINGS_DIR}")

    ingest = PROJECT_ROOT / "scripts" / "ingest_call_recording.py"
    dialogue = PROJECT_ROOT / "scripts" / "build_dialogue_transcripts.py"
    python = sys.executable

    for index, wav_path in enumerate(recordings, start=1):
        print(f"\n[{index}/{len(recordings)}] Transcribing {wav_path.name} (medium model)…")
        subprocess.run(
            [python, str(ingest), str(wav_path), "--output-dir", str(TRANSCRIPTS_DIR)],
            check=True,
        )

    print("\nRebuilding Agent/Prospect dialogue files…")
    subprocess.run([python, str(dialogue)], check=True)
    print("\nDone.")


if __name__ == "__main__":
    main()
