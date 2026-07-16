#!/usr/bin/env python3
"""Compare free OpenRouter models for AI Call Simulator prospect quality."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"

# Curated free candidates (also refreshed from API when possible)
DEFAULT_FREE_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/free",
]

ENGLISH_MARKERS = re.compile(
    r"\b(the|you|your|what|why|how|yes|no|okay|please|sorry|hello|thank|listen|understand|speaking)\b",
    re.I,
)
FRENCH_MARKERS = re.compile(
    r"\b(je|j'|vous|oui|non|c'est|pas|pour|avec|chez|bonjour|monsieur|madame|facture|fournisseur)\b",
    re.I,
)
META_LEAK = re.compile(
    r"prospect|agressif|débutant|ma réponse en tant|language model|as an ai|openrouter",
    re.I,
)

SCENARIOS = [
    {
        "name": "agressif_accroche",
        "system": (
            "Tu es le prospect AGRESSIF au téléphone en France. FRANÇAIS UNIQUEMENT. "
            "1-3 phrases max. Ne répète jamais l'agent. Pas de markdown."
        ),
        "messages": [
            {"role": "assistant", "content": "Oui bonjour ?"},
            {
                "role": "user",
                "content": (
                    "Bonjour monsieur, je suis Émilie de Génie Énergie, comparateur indépendant. "
                    "Je vous appelle pour vérifier si vous êtes bien positionné chez votre fournisseur."
                ),
            },
        ],
        "forbidden_echo": "comparateur indépendant",
    },
    {
        "name": "rgpd_refus",
        "system": (
            "Tu es le prospect RGPD méfiant. FRANÇAIS UNIQUEMENT. 1-3 phrases. "
            "Pose des questions sur l'origine du contact si besoin."
        ),
        "messages": [
            {"role": "assistant", "content": "Oui, qui êtes-vous ?"},
            {
                "role": "user",
                "content": "Je suis de Génie Énergie. Pouvez-vous me donner votre PDL s'il vous plaît ?",
            },
        ],
        "forbidden_echo": "pouvez-vous me donner votre pdl",
    },
    {
        "name": "presse_pitch",
        "system": (
            "Tu es le prospect PRESSÉ. FRANÇAIS UNIQUEMENT. Phrases courtes. "
            "Rappelle que tu manques de temps."
        ),
        "messages": [
            {"role": "assistant", "content": "Oui, j'ai une minute."},
            {
                "role": "user",
                "content": (
                    "Parfait, chez EDF vous payez environ 80 euros, nous avons une offre à 65 euros "
                    "avec Home Énergie, électricité seulement, sans engagement."
                ),
            },
        ],
        "forbidden_echo": "65 euros",
    },
]


@dataclass
class ScenarioResult:
    ok: bool = False
    latency_ms: int = 0
    reply: str = ""
    french: bool = False
    no_echo: bool = False
    in_character: bool = False
    length_ok: bool = False
    error: str = ""


@dataclass
class ModelScore:
    model: str
    scenarios: list[ScenarioResult] = field(default_factory=list)
    total_score: float = 0.0
    avg_latency_ms: float = 0.0
    errors: int = 0

    def compute(self) -> None:
        if not self.scenarios:
            self.total_score = 0.0
            return
        points = 0
        latencies = []
        for s in self.scenarios:
            if not s.ok:
                self.errors += 1
                continue
            latencies.append(s.latency_ms)
            points += int(s.french) + int(s.no_echo) + int(s.in_character) + int(s.length_ok)
        max_points = len(self.scenarios) * 4
        self.total_score = round(100 * points / max_points, 1) if max_points else 0.0
        self.avg_latency_ms = round(sum(latencies) / len(latencies), 0) if latencies else 0.0


def load_env() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_api_key() -> str:
    load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise SystemExit("OPENROUTER_API_KEY manquante dans .env ou l'environnement.")
    return key


def fetch_free_models(api_key: str) -> list[str]:
    req = urllib.request.Request(
        MODELS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return DEFAULT_FREE_MODELS

    free_ids: list[str] = []
    for item in data.get("data", []):
        model_id = item.get("id") or ""
        pricing = item.get("pricing") or {}
        prompt_price = str(pricing.get("prompt", "1"))
        completion_price = str(pricing.get("completion", "1"))
        if model_id.endswith(":free") or (prompt_price == "0" and completion_price == "0"):
            free_ids.append(model_id)

    curated = [m for m in DEFAULT_FREE_MODELS if m in free_ids or m == "openrouter/free"]
    extras = [m for m in free_ids if m not in curated and "lyria" not in m.lower()]
    extras.sort()
    return curated + extras[:8]


def extract_text(data: dict) -> str:
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ).strip()
    return ""


def score_reply(reply: str, forbidden_echo: str) -> tuple[bool, bool, bool, bool]:
    if not reply:
        return False, False, False, False
    french = not (
        ENGLISH_MARKERS.search(reply)
        and (not FRENCH_MARKERS.search(reply) or len(reply) > 20)
    )
    norm_reply = re.sub(r"[^\w\s]", " ", reply.lower())
    norm_forbidden = re.sub(r"[^\w\s]", " ", forbidden_echo.lower())
    no_echo = norm_forbidden not in norm_reply
    in_character = not META_LEAK.search(reply)
    words = reply.split()
    length_ok = 2 <= len(words) <= 80
    return french, no_echo, in_character, length_ok


def call_model(api_key: str, model: str, system: str, messages: list[dict]) -> tuple[str, int, str]:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "max_tokens": 180,
        "temperature": 0.7,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Mahaaa11/Ai-call-simulator",
            "X-Title": "AI Call Simulator benchmark",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        return "", int((time.perf_counter() - started) * 1000), f"HTTP {exc.code}: {detail}"
    except Exception as exc:
        return "", int((time.perf_counter() - started) * 1000), str(exc)

    latency_ms = int((time.perf_counter() - started) * 1000)
    if data.get("error"):
        return "", latency_ms, str(data["error"])
    text = extract_text(data)
    if not text:
        return "", latency_ms, "Réponse vide"
    return text, latency_ms, ""


def benchmark_model(api_key: str, model: str) -> ModelScore:
    score = ModelScore(model=model)
    for scenario in SCENARIOS:
        result = ScenarioResult()
        reply, latency_ms, err = call_model(
            api_key, model, scenario["system"], scenario["messages"]
        )
        result.latency_ms = latency_ms
        result.reply = reply
        if err:
            result.error = err
            score.scenarios.append(result)
            time.sleep(1.2)
            continue
        result.ok = True
        french, no_echo, in_character, length_ok = score_reply(
            reply, scenario["forbidden_echo"]
        )
        result.french = french
        result.no_echo = no_echo
        result.in_character = in_character
        result.length_ok = length_ok
        score.scenarios.append(result)
        time.sleep(1.2)
    score.compute()
    return score


def print_report(scores: list[ModelScore]) -> None:
    ranked = sorted(scores, key=lambda s: (-s.total_score, s.avg_latency_ms))
    print("\n=== Benchmark modèles gratuits OpenRouter (prospect FR) ===\n")
    print(f"{'Modèle':<52} {'Score':>6} {'Latence':>8} {'Err':>4}")
    print("-" * 74)
    for s in ranked:
        print(
            f"{s.model:<52} {s.total_score:>5.1f}% {s.avg_latency_ms:>7.0f}ms {s.errors:>4}"
        )

    if ranked:
        best = ranked[0]
        print(f"\nMeilleur score global : {best.model} ({best.total_score}%)")
        print("\n--- Détail du meilleur modèle ---")
        for scenario, result in zip(SCENARIOS, best.scenarios):
            print(f"\n[{scenario['name']}]")
            if result.error:
                print(f"  ERREUR: {result.error}")
            else:
                print(f"  Réponse: {result.reply[:220]}")
                print(
                    f"  FR={result.french} no_echo={result.no_echo} "
                    f"role={result.in_character} len={result.length_ok} "
                    f"({result.latency_ms}ms)"
                )

    out_path = ROOT / "scripts" / "benchmark_free_models_results.json"
    out_path.write_text(
        json.dumps(
            [
                {
                    "model": s.model,
                    "total_score": s.total_score,
                    "avg_latency_ms": s.avg_latency_ms,
                    "errors": s.errors,
                    "scenarios": [
                        {
                            "name": SCENARIOS[i]["name"],
                            "ok": r.ok,
                            "latency_ms": r.latency_ms,
                            "reply": r.reply,
                            "french": r.french,
                            "no_echo": r.no_echo,
                            "in_character": r.in_character,
                            "length_ok": r.length_ok,
                            "error": r.error,
                        }
                        for i, r in enumerate(s.scenarios)
                    ],
                }
                for s in ranked
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nRésultats JSON : {out_path}")


def main() -> None:
    api_key = get_api_key()
    models = fetch_free_models(api_key)
    if "--quick" in sys.argv:
        models = models[:5]
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        models = sys.argv[1:]

    print(f"Modèles à tester ({len(models)}):")
    for m in models:
        print(f"  - {m}")

    scores: list[ModelScore] = []
    for idx, model in enumerate(models, start=1):
        print(f"\n[{idx}/{len(models)}] Test {model}...")
        scores.append(benchmark_model(api_key, model))

    print_report(scores)


if __name__ == "__main__":
    main()
