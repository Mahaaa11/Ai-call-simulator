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
          training_mode VARCHAR(32) NULL,
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
            try:
                cur.execute("SELECT training_mode FROM conversations LIMIT 1")
            except Exception:
                cur.execute("ALTER TABLE conversations ADD COLUMN training_mode VARCHAR(32) NULL")
            try:
                cur.execute("SELECT agent_name FROM conversations LIMIT 1")
            except Exception:
                cur.execute("ALTER TABLE conversations ADD COLUMN agent_name VARCHAR(128) NULL")
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
    training_mode = (payload.get("training_mode") or "train_agent").strip() or "train_agent"
    agent_name = (payload.get("agent_name") or "").strip() or None
    exam_meta = payload.get("exam_meta") or (evaluation.get("exam_meta") if evaluation else None)
    if not agent_name and isinstance(exam_meta, dict):
        agent_name = (exam_meta.get("agent_name") or "").strip() or None

    score_total = evaluation.get("score_total")
    score_level = evaluation.get("niveau")
    evaluation_json = json.dumps(evaluation, ensure_ascii=False) if evaluation else None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversations (
                  profile_key, level_key, training_mode, model,
                  prospect_first_name, prospect_last_name,
                  agent_name,
                  started_at, ended_at,
                  score_total, score_level, evaluation_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    profile,
                    level,
                    training_mode,
                    model,
                    (persona.get("firstName") or persona.get("first_name") or None),
                    (persona.get("lastName") or persona.get("last_name") or None),
                    agent_name,
                    started_at,
                    ended_at,
                    score_total,
                    score_level,
                    evaluation_json,
                ),
            )
            conversation_id = cur.lastrowid

            rows = []
            for idx, msg in enumerate(messages):
                role = (msg.get("role") or "").lower()
                if training_mode == "train_prospect":
                    speaker = "prospect" if role in ("user", "prospect") else "agent"
                else:
                    speaker = "agent" if role in ("user", "agent") else "prospect"
                content = (msg.get("content") or "").strip()
                if not content:
                    continue
                rows.append((conversation_id, idx, speaker, content))

            if rows:
                cur.executemany(
                    """
                    INSERT INTO conversation_messages (conversation_id, seq, speaker, content)
                    VALUES (%s, %s, %s, %s)
                    """,
                    rows,
                )

        return int(conversation_id)
    finally:
        conn.close()


def update_conversation_evaluation(conversation_id: int, evaluation: dict) -> None:
    ensure_schema()
    score_total = evaluation.get("score_total")
    score_level = evaluation.get("niveau")
    evaluation_json = json.dumps(evaluation, ensure_ascii=False) if evaluation else None
    exam_meta = evaluation.get("exam_meta") if isinstance(evaluation, dict) else None
    agent_name = None
    if isinstance(exam_meta, dict):
        agent_name = (exam_meta.get("agent_name") or "").strip() or None

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if agent_name:
                cur.execute(
                    """
                    UPDATE conversations
                    SET score_total = %s, score_level = %s, evaluation_json = %s, agent_name = %s
                    WHERE id = %s
                    """,
                    (score_total, score_level, evaluation_json, agent_name, conversation_id),
                )
            else:
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


def count_conversations() -> int:
    ensure_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM conversations")
            row = cur.fetchone()
            return int(row["total"] if isinstance(row, dict) else row[0])
    finally:
        conn.close()


def list_conversations(limit: int = 50) -> list[dict]:
    ensure_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_name, profile_key, level_key, training_mode, model,
                       prospect_first_name, prospect_last_name,
                       score_total, score_level, created_at
                FROM conversations
                ORDER BY id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def list_exam_certified_conversations(
    *,
    min_score: int = 70,
    exam_date: str | None = "2026-07-17",
    limit: int = 500,
) -> list[dict]:
    """Return exam calls that meet the certification threshold."""
    ensure_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT id, agent_name, profile_key, level_key, training_mode, model,
                       prospect_first_name, prospect_last_name,
                       score_total, score_level, evaluation_json,
                       started_at, ended_at, created_at
                FROM conversations
                WHERE score_total IS NOT NULL
                  AND score_total >= %s
                  AND (
                    training_mode = 'exam_certif'
                    OR (
                      profile_key = 'mefiant_fournisseur'
                      AND level_key = 'avance'
                      AND prospect_first_name = 'Philippe'
                      AND prospect_last_name = 'Bernard'
                    )
                  )
            """
            params: list = [min_score]
            if exam_date:
                sql += " AND DATE(created_at) = %s"
                params.append(exam_date)
            sql += " ORDER BY score_total DESC, id DESC LIMIT %s"
            params.append(limit)
            cur.execute(sql, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def get_conversation(conversation_id: int) -> dict | None:
    ensure_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM conversations WHERE id = %s", (conversation_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_conversation_messages(conversation_id: int) -> list[dict]:
    ensure_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT seq, speaker, content
                FROM conversation_messages
                WHERE conversation_id = %s
                ORDER BY seq
                """,
                (conversation_id,),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def list_conversations_for_agent(agent_name: str, *, limit: int = 100) -> list[dict]:
    name = (agent_name or "").strip()
    if not name:
        return []
    ensure_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, agent_name, profile_key, level_key, training_mode, model,
                       prospect_first_name, prospect_last_name,
                       score_total, score_level, created_at
                FROM conversations
                WHERE LOWER(agent_name) LIKE LOWER(%s)
                ORDER BY id DESC
                LIMIT %s
                """,
                (f"%{name}%", limit),
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def count_conversations_for_agent(agent_name: str) -> int:
    name = (agent_name or "").strip()
    if not name:
        return 0
    ensure_schema()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM conversations
                WHERE LOWER(agent_name) LIKE LOWER(%s)
                """,
                (f"%{name}%",),
            )
            row = cur.fetchone()
            return int(row["total"] if isinstance(row, dict) else row[0])
    finally:
        conn.close()


def list_conversations_by_agent_names(
    names: list[str],
    *,
    limit_per_agent: int = 5,
) -> dict[str, list[dict]]:
    """Return the most recent conversations for each requested agent name."""
    cleaned = [n.strip() for n in names if n and n.strip()]
    if not cleaned:
        return {}

    ensure_schema()
    conn = get_connection()
    result: dict[str, list[dict]] = {}
    try:
        with conn.cursor() as cur:
            for name in cleaned:
                cur.execute(
                    """
                    SELECT id, agent_name, profile_key, level_key, training_mode, model,
                           prospect_first_name, prospect_last_name,
                           score_total, score_level, evaluation_json,
                           started_at, ended_at, created_at
                    FROM conversations
                    WHERE LOWER(agent_name) LIKE LOWER(%s)
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (f"%{name}%", limit_per_agent),
                )
                rows = list(cur.fetchall())
                if rows:
                    result[name] = rows
    finally:
        conn.close()
    return result
