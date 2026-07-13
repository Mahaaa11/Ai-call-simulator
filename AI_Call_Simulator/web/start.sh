#!/usr/bin/env bash
# Démarre MySQL (Docker), TTS, API conversations et le serveur HTTP pour simulation.html
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== Simulateur web — AI_Call_Simulator/web ==="

if command -v docker >/dev/null 2>&1; then
  docker compose up -d 2>/dev/null || docker-compose up -d 2>/dev/null || true
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Créé web/.env depuis .env.example"
fi

pip3 install -q pymysql edge-tts 2>/dev/null || pip install -q pymysql edge-tts

kill_port() { lsof -ti :"$1" | xargs kill -9 2>/dev/null || true; }

kill_port 8765
kill_port 8766
kill_port 8080

python3 "$ROOT/tts_server.py" &
python3 "$ROOT/conversation_api.py" &
python3 -m http.server 8080 &

echo ""
echo "  Page      : http://localhost:8080/simulation.html"
echo "  TTS       : http://127.0.0.1:8765/health"
echo "  MySQL API : http://127.0.0.1:8766/health"
echo ""
echo "Ctrl+C pour arrêter — puis : kill \$(lsof -ti :8080,:8765,:8766)"

wait
