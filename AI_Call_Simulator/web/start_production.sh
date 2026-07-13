#!/usr/bin/env bash
# Démarre conversation_api + tts_server en production (sans Docker)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "ERREUR: copiez .env.production.example vers .env et configurez MYSQL_HOST"
  exit 1
fi

export BIND_HOST="${BIND_HOST:-0.0.0.0}"

pip3 install -q pymysql edge-tts 2>/dev/null || pip install -q pymysql edge-tts

kill_port() { lsof -ti :"$1" | xargs kill -9 2>/dev/null || true; }
kill_port 8765
kill_port 8766

echo "=== Test connexion MySQL ==="
python3 - <<'PY'
import os
from pathlib import Path

def load_env():
    for p in [Path("config/connexion_mysql.env"), Path(".env")]:
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

load_env()
import pymysql
cfg = dict(
    host=os.getenv("MYSQL_HOST", "127.0.0.1"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASSWORD", ""),
    database=os.getenv("MYSQL_DATABASE", "call_simulator"),
)
ssl_on = os.getenv("MYSQL_SSL", "").lower() in ("1", "true", "yes")
if ssl_on:
    cfg["ssl"] = {"ssl": True}
conn = pymysql.connect(**cfg)
conn.close()
print(f"OK — {cfg['host']}:{cfg['port']} / {cfg['database']}")
PY

python3 "$ROOT/conversation_api.py" &
python3 "$ROOT/tts_server.py" &

echo ""
echo "  API MySQL : http://127.0.0.1:8766/health"
echo "  TTS       : http://127.0.0.1:8765/health"
echo "  Nginx doit proxy : /conv-api/ → 8766 et /tts/ → 8765"
echo ""
wait
