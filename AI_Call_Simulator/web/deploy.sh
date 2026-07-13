#!/usr/bin/env bash
# Déploiement production du simulateur (Docker Compose)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker est requis. Installez Docker Desktop ou Docker Engine."
  exit 1
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Créé web/.env depuis .env.example"
fi

COMPOSE_FILE="docker-compose.prod.yml"
if docker compose version >/dev/null 2>&1; then
  DC="docker compose -f $COMPOSE_FILE"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose -f $COMPOSE_FILE"
else
  echo "docker compose introuvable."
  exit 1
fi

echo "=== Build & démarrage du simulateur ==="
$DC build --pull
$DC up -d

PORT="${HTTP_PORT:-80}"
echo ""
echo "  Simulateur : http://localhost:${PORT}/simulation.html"
echo "  TTS health : http://localhost:${PORT}/tts/health"
echo "  API health : http://localhost:${PORT}/conv-api/health"
echo ""
echo "Logs : $DC logs -f"
echo "Stop : $DC down"
