#!/usr/bin/env python3
"""Export prospect training data from all transcribed calls + knowledge base."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS_DIR = PROJECT_ROOT / "data" / "call_transcripts"
KNOWLEDGE_PATH = PROJECT_ROOT / "data" / "knowledge_base.json"
OUTPUT_DIR = PROJECT_ROOT / "data" / "training"

SYSTEM_PROMPT = """Tu es le PROSPECT (client) dans un appel sortant de vente d'énergie en français.
Tu n'es PAS le commercial. Réponds en 1 ou 2 phrases courtes, naturelles, orales.
Réponds directement à la question de l'agent (oui/non, chiffre, fournisseur, mail reçu ou non)."""


def load_dialogue_pairs() -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for path in sorted(TRANSCRIPTS_DIR.glob("*_dialogue.json")):
        try:
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (json.JSONDecodeError, OSError):
            continue

        turns = payload.get("turns", [])
        call_id = path.stem.replace("_dialogue", "")
        for index, turn in enumerate(turns):
            if turn.get("role") != "agent":
                continue
            if index + 1 >= len(turns):
                continue
            next_turn = turns[index + 1]
            if next_turn.get("role") != "prospect":
                continue
            agent = str(turn.get("text", "")).strip()
            prospect = str(next_turn.get("text", "")).strip()
            if len(agent) < 8 or len(prospect) < 2:
                continue
            if len(agent.split()) > 120 or len(prospect.split()) > 40:
                continue
            pairs.append({"agent": agent, "prospect": prospect, "source": call_id})
    return pairs


def load_kb_pairs() -> list[dict[str, str]]:
    if not KNOWLEDGE_PATH.exists():
        return []
    payload = json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))
    pairs: list[dict[str, str]] = []
    for item in payload.get("objections", []):
        agent = str(item.get("expected_answer", "")).strip()
        for key in ("easy_reaction", "intermediate_reaction", "difficult_reaction"):
            prospect = str(item.get(key, "")).strip()
            if agent and prospect:
                pairs.append(
                    {
                        "agent": agent,
                        "prospect": prospect,
                        "source": f"kb:{item.get('profile', '')}:{key}",
                    }
                )
    return pairs


def to_chat_record(agent: str, prospect: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": agent},
            {"role": "assistant", "content": prospect},
        ]
    }


def to_alpaca_record(agent: str, prospect: str) -> dict:
    return {
        "instruction": SYSTEM_PROMPT,
        "input": agent,
        "output": prospect,
    }


def sample_for_modelfile(pairs: list[dict[str, str]], limit: int, per_call: int) -> list[dict[str, str]]:
    """Pick diverse examples across all calls (not just the first files)."""
    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for pair in pairs:
        if pair["source"].startswith("kb:"):
            by_source["__kb__"].append(pair)
        else:
            by_source[pair["source"]].append(pair)

    rng = random.Random(42)
    sampled: list[dict[str, str]] = []

    call_sources = [key for key in by_source if key != "__kb__"]
    rng.shuffle(call_sources)

    for source in call_sources:
        pool = by_source[source]
        rng.shuffle(pool)
        sampled.extend(pool[:per_call])

    kb_pool = by_source.get("__kb__", [])
    rng.shuffle(kb_pool)
    sampled.extend(kb_pool[: min(30, len(kb_pool))])

    rng.shuffle(sampled)
    return sampled[:limit]


def build_modelfile(records: list[dict], base_model: str = "qwen2.5:7b") -> str:
    lines = [
        f"FROM {base_model}",
        "",
        f'SYSTEM """{SYSTEM_PROMPT}"""',
        "",
        "PARAMETER temperature 0.35",
        "PARAMETER num_ctx 8192",
        "",
    ]
    for record in records:
        agent = record["messages"][1]["content"].replace('"', '\\"').replace("\n", " ")
        prospect = record["messages"][2]["content"].replace('"', '\\"').replace("\n", " ")
        if len(agent) > 400:
            agent = agent[:397] + "..."
        lines.append(f'MESSAGE user "{agent}"')
        lines.append(f'MESSAGE assistant "{prospect}"')
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build prospect training dataset from all calls.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--modelfile-limit", type=int, default=250)
    parser.add_argument("--per-call", type=int, default=15, help="Max examples per call in Modelfile.")
    parser.add_argument("--base-model", default="qwen2.5:7b")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    dialogue_pairs = load_dialogue_pairs()
    kb_pairs = load_kb_pairs()
    all_pairs = dialogue_pairs + kb_pairs

    calls = {pair["source"] for pair in dialogue_pairs}

    jsonl_path = args.output_dir / "prospect_pairs.jsonl"
    alpaca_path = args.output_dir / "prospect_alpaca.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as file:
        for pair in all_pairs:
            file.write(json.dumps(to_chat_record(pair["agent"], pair["prospect"]), ensure_ascii=False) + "\n")
    with alpaca_path.open("w", encoding="utf-8") as file:
        for pair in all_pairs:
            file.write(json.dumps(to_alpaca_record(pair["agent"], pair["prospect"]), ensure_ascii=False) + "\n")

    modelfile_sample = sample_for_modelfile(all_pairs, args.modelfile_limit, args.per_call)
    records = [to_chat_record(pair["agent"], pair["prospect"]) for pair in modelfile_sample]
    modelfile_path = args.output_dir / "Modelfile.prospect-energie"
    modelfile_path.write_text(build_modelfile(records, args.base_model), encoding="utf-8")

    meta = {
        "calls_transcrits": len(calls),
        "dialogue_pairs": len(dialogue_pairs),
        "knowledge_pairs": len(kb_pairs),
        "total_pairs": len(all_pairs),
        "modelfile_examples": len(records),
        "jsonl": str(jsonl_path),
        "alpaca_jsonl": str(alpaca_path),
        "modelfile": str(modelfile_path),
        "calls": sorted(calls),
    }
    (args.output_dir / "dataset_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps({k: v for k, v in meta.items() if k != "calls"}, indent=2, ensure_ascii=False))
    print(f"Appels sources: {len(calls)}")
    if calls:
        print("  " + ", ".join(sorted(calls)[:5]) + ("..." if len(calls) > 5 else ""))


if __name__ == "__main__":
    main()
