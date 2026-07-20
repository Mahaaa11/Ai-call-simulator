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
pip3 install -q -r "$ROOT/requirements-avatar.txt" 2>/dev/null || pip install -q -r "$ROOT/requirements-avatar.txt" 2>/dev/null || true

kill_port() { lsof -ti :"$1" | xargs kill -9 2>/dev/null || true; }

kill_port 8765
kill_port 8766
kill_port 8767
kill_port 8080

# FastAPI avatar + TTS (WebSocket, MuseTalk-ready). Falls back to loop videos without GPU.
python3 "$ROOT/run_avatar_server.py" &
python3 "$ROOT/conversation_api.py" &
python3 -m http.server 8080 &

echo ""
echo "  Page      : http://localhost:8080/simulation.html"
echo "  Avatar API: http://127.0.0.1:8767/health  (TTS + WebSocket ws://127.0.0.1:8767/ws/avatar)"
echo "  MySQL API : http://127.0.0.1:8766/health"
echo ""
echo "  MuseTalk  : AVATAR_BACKEND=musetalk MUSETALK_URL=http://127.0.0.1:8780"
echo "  Idle face : AVATAR_BACKEND=musetalk+liveportrait LIVEPORTRAIT_URL=http://127.0.0.1:8781"
echo ""
echo "Ctrl+C pour arrêter — puis : kill \$(lsof -ti :8080,:8766,:8767)"

wait
