#!/usr/bin/env python3
"""Transcrire en masse vos appels (AssemblyAI) → dialogues agent/prospect."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from engine.assemblyai_transcriber import ProTranscriptionError, save_transcription, transcribe_call

RAW_CALLS_DIR = PROJECT_ROOT / "data" / "raw_calls"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference_recordings"
TRANSCRIPTS_DIR = PROJECT_ROOT / "data" / "call_transcripts"
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}


def load_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def discover_audio_files(dirs: list[Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for directory in dirs:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            key = path.stem.lower()
            if key in seen:
                continue
            seen.add(key)
            files.append(path)
    return files


def already_transcribed(stem: str, output_dir: Path) -> bool:
    return (output_dir / f"{stem}_dialogue.json").exists()


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(
        description="Transcription batch AssemblyAI (français + diarisation agent/prospect)."
    )
    parser.add_argument(
        "audio",
        nargs="*",
        type=Path,
        help="Fichiers audio. Sans argument: data/raw_calls/ + data/reference_recordings/",
    )
    parser.add_argument("--output-dir", type=Path, default=TRANSCRIPTS_DIR)
    parser.add_argument("--force", action="store_true", help="Retranscrire même si déjà fait.")
    parser.add_argument("--dry-run", action="store_true", help="Lister les fichiers sans transcrire.")
    parser.add_argument("--limit", type=int, default=0, help="Max fichiers à traiter (0 = tous).")
    args = parser.parse_args()

    if args.audio:
        files = [path.resolve() for path in args.audio]
    else:
        files = discover_audio_files([RAW_CALLS_DIR, REFERENCE_DIR])

    if not files:
        print("Aucun fichier audio trouvé.")
        print(f"  → Déposez vos WAV/MP3 dans: {RAW_CALLS_DIR}")
        raise SystemExit(1)

    pending = [
        path
        for path in files
        if args.force or not already_transcribed(path.stem, args.output_dir)
    ]
    skipped = len(files) - len(pending)
    if args.limit > 0:
        pending = pending[: args.limit]

    print(f"Audio trouvés: {len(files)} | À transcrire: {len(pending)} | Déjà faits: {skipped}")

    if args.dry_run:
        for path in pending:
            print(f"  [pending] {path}")
        for path in files:
            if path not in pending:
                print(f"  [skip]    {path.name}")
        return

    if not pending:
        print("Rien à transcrire. Utilisez --force pour refaire.")
        return

    ok = 0
    errors = 0
    started = time.time()

    for index, audio_path in enumerate(pending, start=1):
        if not audio_path.exists():
            print(f"[{index}/{len(pending)}] Ignoré (introuvable): {audio_path}")
            errors += 1
            continue

        print(f"\n[{index}/{len(pending)}] {audio_path.name}")
        try:
            payload = transcribe_call(audio_path)
            _, dialogue_path = save_transcription(payload, args.output_dir, audio_path.stem)
            turns = len(payload["turns"])
            pairs = sum(
                1
                for i, turn in enumerate(payload["turns"])
                if turn["role"] == "agent"
                and i + 1 < len(payload["turns"])
                and payload["turns"][i + 1]["role"] == "prospect"
            )
            print(f"  OK → {dialogue_path.name} ({turns} tours, {pairs} paires agent→prospect)")
            ok += 1
        except ProTranscriptionError as exc:
            print(f"  ERREUR: {exc}")
            errors += 1
            if "Clé AssemblyAI manquante" in str(exc):
                raise SystemExit(1) from exc

    elapsed = time.time() - started
    print(f"\nTerminé en {elapsed:.0f}s — {ok} OK, {errors} erreur(s)")
    print("Étape suivante:")
    print("  python scripts/build_prospect_training_data.py")
    print("  bash scripts/create_prospect_model.sh")


if __name__ == "__main__":
    main()
