#!/usr/bin/env bash
# Pipeline complet: vos appels → transcriptions → dataset → modèle Ollama prospect-energie
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RAW="$ROOT/data/raw_calls"
mkdir -p "$RAW"

echo "═══════════════════════════════════════════════════════════"
echo "  Import & entraînement prospect — AI Call Simulator"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Dossier appels: $RAW"
echo "  (WAV, MP3, M4A, OGG — autant de fichiers que vous voulez)"
echo ""

COUNT=$(find "$RAW" "$ROOT/data/reference_recordings" -type f \( -iname '*.wav' -o -iname '*.mp3' -o -iname '*.m4a' \) 2>/dev/null | wc -l | tr -d ' ')
echo "Fichiers audio détectés: $COUNT"
echo ""

if [[ "${1:-}" != "--skip-transcribe" ]]; then
  echo "→ Étape 1/3 : Transcription AssemblyAI (peut prendre plusieurs minutes)..."
  .venv/bin/python scripts/batch_transcribe_calls.py "$@"
else
  echo "→ Étape 1/3 : Transcription ignorée (--skip-transcribe)"
fi

echo ""
echo "→ Étape 2/3 : Construction du dataset d'entraînement..."
.venv/bin/python scripts/build_prospect_training_data.py

echo ""
echo "→ Étape 3/3 : Création du modèle Ollama prospect-energie..."
bash scripts/create_prospect_model.sh

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Terminé !"
echo "  • Dataset: data/training/prospect_pairs.jsonl"
echo "  • Modèle:  ollama run prospect-energie"
echo "  • App:     Streamlit → modèle « prospect-energie (fine-tuné) »"
echo "  • Ou laissez le Moteur v5 (recommandé pour les tests)"
echo "═══════════════════════════════════════════════════════════"
