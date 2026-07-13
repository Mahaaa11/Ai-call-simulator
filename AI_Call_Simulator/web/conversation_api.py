#!/usr/bin/env python3
"""API MySQL pour enregistrer les conversations du simulateur (simulation.html)."""
import json
import os
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

try:
    import pymysql
except ImportError:
    print("Installation requise : pip install pymysql")
    raise SystemExit(1)

PORT = int(os.getenv("API_PORT", "8766"))
BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")
ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env_file():
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "call_simulator"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def get_server_connection():
    cfg = {k: v for k, v in DB_CONFIG.items() if k != "database"}
    return pymysql.connect(**cfg)


def ensure_database():
    db_name = DB_CONFIG["database"]
    conn = get_server_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()


def ensure_schema():
    ddl_conversations = """
        CREATE TABLE IF NOT EXISTS conversations (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          profile_key VARCHAR(64) NOT NULL,
          level_key VARCHAR(32) NOT NULL,
          model VARCHAR(128) NULL,
          prospect_first_name VARCHAR(64) NULL,
          prospect_last_name VARCHAR(64) NULL,
          started_at DATETIME NULL,
          ended_at DATETIME NULL,
          score_total INT NULL,
          score_level VARCHAR(64) NULL,
          evaluation_json JSON NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_conversations_created (created_at),
          INDEX idx_conversations_profile (profile_key, level_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    ddl_messages = """
        CREATE TABLE IF NOT EXISTS conversation_messages (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          conversation_id BIGINT UNSIGNED NOT NULL,
          seq INT UNSIGNED NOT NULL,
          speaker ENUM('agent', 'prospect') NOT NULL,
          content TEXT NOT NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT fk_messages_conversation
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            ON DELETE CASCADE,
          INDEX idx_messages_conversation (conversation_id, seq)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(ddl_conversations)
            cur.execute(ddl_messages)
    finally:
        conn.close()


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def save_conversation(payload):
    profile = (payload.get("profile") or "").strip() or "unknown"
    level = (payload.get("level") or "").strip() or "unknown"
    model = (payload.get("model") or "").strip() or None
    started_at = parse_dt(payload.get("started_at"))
    ended_at = parse_dt(payload.get("ended_at"))
    persona = payload.get("persona") or {}
    evaluation = payload.get("evaluation") or {}
    messages = payload.get("messages") or []

    score_total = evaluation.get("score_total")
    score_level = evaluation.get("niveau")
    evaluation_json = json.dumps(evaluation, ensure_ascii=False) if evaluation else None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (
                  profile_key, level_key, model,
                  prospect_first_name, prospect_last_name,
                  started_at, ended_at,
                  score_total, score_level, evaluation_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    profile,
                    level,
                    model,
                    (persona.get("firstName") or persona.get("first_name") or None),
                    (persona.get("lastName") or persona.get("last_name") or None),
                    started_at,
                    ended_at,
                    score_total,
                    score_level,
                    evaluation_json,
                ),
            )
            conversation_id = cur.lastrowid

            for idx, msg in enumerate(messages):
                role = (msg.get("role") or "").lower()
                speaker = "agent" if role in ("user", "agent") else "prospect"
                content = (msg.get("content") or "").strip()
                if not content:
                    continue
                cur.execute(
                    """
                    INSERT INTO conversation_messages (conversation_id, seq, speaker, content)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (conversation_id, idx, speaker, content),
                )

        return conversation_id
    finally:
        conn.close()


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
            try:
                conn = get_connection()
                conn.close()
                self._json_response(200, {"ok": True, "database": DB_CONFIG["database"]})
            except Exception as e:
                self._json_response(503, {"ok": False, "error": str(e)})
            return

        if path == "/api/conversations":
            limit = 20
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if qs.get("limit"):
                try:
                    limit = max(1, min(100, int(qs["limit"][0])))
                except ValueError:
                    pass
            try:
                conn = get_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, profile_key, level_key, score_total, score_level, started_at, ended_at, created_at
                        FROM conversations
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    rows = cur.fetchall()
                conn.close()
                for row in rows:
                    for key, val in row.items():
                        if isinstance(val, datetime):
                            row[key] = val.isoformat(sep=" ", timespec="seconds")
                self._json_response(200, {"conversations": rows})
            except Exception as e:
                self._json_response(500, {"ok": False, "error": str(e)})
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
    print(f"  host={DB_CONFIG['host']}:{DB_CONFIG['port']} db={DB_CONFIG['database']} user={DB_CONFIG['user']}")
    try:
        ensure_database()
        ensure_schema()
        conn = get_connection()
        conn.close()
        print("Connexion MySQL : OK")
    except Exception as e:
        print(f"Connexion MySQL : ÉCHEC — {e}")
        print("Option A — Docker : cd AI_Call_Simulator/web && docker compose up -d")
        print("Option B — MySQL local : mysql -u root -p < mysql_schema.sql")
        print("Puis copiez .env.example en .env et adaptez MYSQL_PASSWORD")
    print(f"API conversations : http://127.0.0.1:{PORT}/api/conversations")
    print(f"Santé           : http://127.0.0.1:{PORT}/health")
    print("Laissez ce terminal ouvert pendant la simulation.")
    HTTPServer((BIND_HOST, PORT), ConversationHandler).serve_forever()
