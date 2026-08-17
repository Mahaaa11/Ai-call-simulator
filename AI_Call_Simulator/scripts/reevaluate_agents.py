#!/usr/bin/env python3
"""Re-evaluate stored conversations with improved compliance rules."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from evaluation_engine import reevaluate_from_messages  # noqa: E402
from mysql_store import (  # noqa: E402
    find_latest_conversations_for_agents,
    get_conversation,
    get_conversation_messages,
    resolve_conversation_agent_name,
    update_conversation_evaluation,
)


def _load_env() -> None:
    for path in (
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / "web" / ".env",
        PROJECT_ROOT / "config" / "connexion_mysql.env",
    ):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _parse_eval(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def find_conversations(agent_queries: list[str], limit_per_agent: int = 1) -> list[dict]:
    """Dernière(s) conversation(s) par agent — recherche flexible (colonne + exam_meta)."""
    return find_latest_conversations_for_agents(
        agent_queries,
        per_agent=max(1, limit_per_agent),
        scan_limit=500,
    )


def reevaluate_conversation(conversation_id: int, *, dry_run: bool = False) -> dict:
    conv = get_conversation(conversation_id)
    if not conv:
        raise ValueError(f"Conversation {conversation_id} introuvable")
    messages = get_conversation_messages(conversation_id)
    prev = _parse_eval(conv.get("evaluation_json"))
    old_score = conv.get("score_total")
    evaluation = reevaluate_from_messages(messages, prev)
    agent = resolve_conversation_agent_name(conv) or conv.get("agent_name")
    if not dry_run:
        update_conversation_evaluation(conversation_id, evaluation)
    return {
        "id": conversation_id,
        "agent_name": agent,
        "old_score": old_score,
        "new_score": evaluation.get("score_total"),
        "new_level": evaluation.get("niveau"),
        "compliance": evaluation.get("_compliance", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-evaluate agent conversations in MySQL/TiDB")
    parser.add_argument(
        "--agents",
        default="Marc,Hassan,Mohamed Anas",
        help="Agent names (comma-separated)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Max conversations per agent (1 = dernière conversation)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Compute only, do not write to DB")
    parser.add_argument("--id", type=int, help="Re-evaluate a single conversation id")
    args = parser.parse_args()

    _load_env()

    if args.id:
        result = reevaluate_conversation(args.id, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    targets = [a.strip() for a in args.agents.split(",") if a.strip()]
    convs = find_conversations(targets, limit_per_agent=args.limit)
    if not convs:
        print("Aucune conversation trouvée pour:", ", ".join(targets))
        return 1

    results = []
    for conv in convs:
        cid = int(conv["id"])
        try:
            results.append(reevaluate_conversation(cid, dry_run=args.dry_run))
        except Exception as exc:
            results.append({"id": cid, "error": str(exc)})

    print(json.dumps(results, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("\n(dry-run — aucune écriture en base)")
    else:
        print(f"\n{len(results)} conversation(s) réévaluée(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
