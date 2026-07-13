#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "→ Génération du dataset (appels + knowledge base)..."
.venv/bin/python scripts/build_prospect_training_data.py --modelfile-limit 250 --per-call 15

MODELFILE="$ROOT/data/training/Modelfile.prospect-energie"
if [[ ! -f "$MODELFILE" ]]; then
  echo "Modelfile introuvable: $MODELFILE" >&2
  exit 1
fi

echo "→ Téléchargement du modèle de base (si nécessaire)..."
ollama pull qwen2.5:7b

echo "→ Création du modèle Ollama prospect-energie..."
ollama create prospect-energie -f "$MODELFILE"

echo ""
echo "Modèle créé: prospect-energie"
echo "Test: ollama run prospect-energie"
echo "Dans l'app Streamlit, choisissez « prospect-energie (fine-tuné) »."
