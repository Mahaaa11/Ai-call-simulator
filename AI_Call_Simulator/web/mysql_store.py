"""MySQL persistence for simulator conversations."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

try:
    import pymysql
except ImportError:
    pymysql = None  # type: ignore

CONFIG_ENV_PATH = Path(__file__).resolve().parents[1] / "config" / "connexion_mysql.env"
WEB_ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def apply_mysql_env_from_mapping(values: dict[str, str]) -> None:
    for key, value in values.items():
        if value:
            os.environ[key] = str(value).strip()


def _mysql_connect_kwargs(include_database: bool = True) -> dict:
    if pymysql is None:
        raise RuntimeError("pymysql requis : pip install pymysql")

    cfg: dict = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True,
    }
    if include_database:
        cfg["database"] = os.getenv("MYSQL_DATABASE", "call_simulator")
    if os.getenv("MYSQL_SSL", "").lower() in ("1", "true", "yes"):
        cfg["ssl"] = {"ssl": True}
    return cfg


def get_connection():
    load_env_file(CONFIG_ENV_PATH)
    load_env_file(WEB_ENV_PATH)
    return pymysql.connect(**_mysql_connect_kwargs(True))


def get_server_connection():
    load_env_file(CONFIG_ENV_PATH)
    load_env_file(WEB_ENV_PATH)
    return pymysql.connect(**_mysql_connect_kwargs(False))


def _skip_create_database() -> bool:
    if os.getenv("MYSQL_SKIP_CREATE_DATABASE", "").lower() in ("1", "true", "yes"):
        return True
    host = os.getenv("MYSQL_HOST", "").lower()
    return "tidbcloud.com" in host or "tidb." in host


def ensure_database() -> None:
    if _skip_create_database():
        return
    db_name = os.getenv("MYSQL_DATABASE", "call_simulator")
    conn = get_server_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()


_SCHEMA_READY = False


def ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    ddl_conversations = """
        CREATE TABLE IF NOT EXISTS conversations (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
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
        )
    """
    ddl_messages = """
        CREATE TABLE IF NOT EXISTS conversation_messages (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          conversation_id BIGINT NOT NULL,
          seq INT NOT NULL,
          speaker VARCHAR(16) NOT NULL,
          content TEXT NOT NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_messages_conversation (conversation_id, seq)
        )
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(ddl_conversations)
            cur.execute(ddl_messages)
    finally:
        conn.close()
    _SCHEMA_READY = True


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


def save_conversation(payload: dict) -> int:
    ensure_schema()

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

        return int(conversation_id)
    finally:
        conn.close()


def update_conversation_evaluation(conversation_id: int, evaluation: dict) -> None:
    ensure_schema()
    score_total = evaluation.get("score_total")
    score_level = evaluation.get("niveau")
    evaluation_json = json.dumps(evaluation, ensure_ascii=False) if evaluation else None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE conversations
                SET score_total = %s, score_level = %s, evaluation_json = %s
                WHERE id = %s
                """,
                (score_total, score_level, evaluation_json, conversation_id),
            )
    finally:
        conn.close()


def check_mysql_connection() -> tuple[bool, str]:
    try:
        ensure_schema()
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.close()
        db_name = os.getenv("MYSQL_DATABASE", "call_simulator")
        return True, db_name
    except Exception as exc:
        return False, str(exc)
