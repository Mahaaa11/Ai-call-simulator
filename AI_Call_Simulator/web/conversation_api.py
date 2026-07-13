#!/usr/bin/env python3
"""API MySQL pour enregistrer les conversations du simulateur (simulation.html)."""
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

try:
    import pymysql
except ImportError:
    print("Installation requise : pip install pymysql")
    raise SystemExit(1)

from mysql_store import check_mysql_connection, save_conversation

PORT = int(os.getenv("API_PORT", "8766"))
BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")
ENV_PATH = Path(__file__).resolve().parent / ".env"
CONFIG_ENV_PATH = Path(__file__).resolve().parents[1] / "config" / "connexion_mysql.env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(CONFIG_ENV_PATH)
load_env_file(ENV_PATH)

DB_NAME = os.getenv("MYSQL_DATABASE", "call_simulator")


class ConversationHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _json_response(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/health":
            ok, detail = check_mysql_connection()
            if ok:
                self._json_response(200, {"ok": True, "database": detail})
            else:
                self._json_response(503, {"ok": False, "error": detail})
            return

        self._json_response(404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/conversations":
            self._json_response(404, {"ok": False, "error": "Not found"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            self._json_response(400, {"ok": False, "error": "JSON invalide"})
            return

        try:
            conversation_id = save_conversation(payload)
            self._json_response(201, {"ok": True, "conversation_id": conversation_id})
        except Exception as e:
            print("Erreur save:", e)
            self._json_response(500, {"ok": False, "error": str(e)})


if __name__ == "__main__":
    print("Configuration MySQL :")
    print(
        f"  host={os.getenv('MYSQL_HOST', '127.0.0.1')}:{os.getenv('MYSQL_PORT', '3306')} "
        f"db={DB_NAME} user={os.getenv('MYSQL_USER', 'root')}"
    )
    ok, detail = check_mysql_connection()
    if ok:
        print(f"Connexion MySQL : OK ({detail})")
    else:
        print(f"Connexion MySQL : ÉCHEC — {detail}")
        print("Copiez .env.production.example en .env et configurez MYSQL_HOST")
    print(f"API conversations : http://127.0.0.1:{PORT}/api/conversations")
    print(f"Santé           : http://127.0.0.1:{PORT}/health")
    HTTPServer((BIND_HOST, PORT), ConversationHandler).serve_forever()
