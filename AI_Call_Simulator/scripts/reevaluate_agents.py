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
    get_conversation,
    get_conversation_messages,
    list_conversations_by_agent_names,
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


def _match_agent(agent_name: str, targets: list[str]) -> bool:
    name = (agent_name or "").lower()
    for t in targets:
        tl = t.lower()
        if tl in name:
            return True
        parts = tl.split()
        if len(parts) >= 2 and all(p in name for p in parts):
            return True
    return False


def find_conversations(agent_queries: list[str], limit_per_agent: int = 3) -> list[dict]:
    seen: set[int] = set()
    rows: list[dict] = []
    for query in agent_queries:
        grouped = list_conversations_by_agent_names([query], limit_per_agent=limit_per_agent)
        for convs in grouped.values():
            for conv in convs:
                cid = int(conv["id"])
                if cid in seen:
                    continue
                if not _match_agent(conv.get("agent_name") or "", agent_queries):
                    continue
                seen.add(cid)
                rows.append(conv)
    rows.sort(key=lambda r: r.get("id", 0), reverse=True)
    return rows


def reevaluate_conversation(conversation_id: int, *, dry_run: bool = False) -> dict:
    conv = get_conversation(conversation_id)
    if not conv:
        raise ValueError(f"Conversation {conversation_id} introuvable")
    messages = get_conversation_messages(conversation_id)
    prev = _parse_eval(conv.get("evaluation_json"))
    old_score = conv.get("score_total")
    evaluation = reevaluate_from_messages(messages, prev)
    if not dry_run:
        update_conversation_evaluation(conversation_id, evaluation)
    return {
        "id": conversation_id,
        "agent_name": conv.get("agent_name"),
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
    parser.add_argument("--limit", type=int, default=3, help="Max conversations per search term")
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
