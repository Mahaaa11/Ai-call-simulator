"""Load real call dialogues (AssemblyAI) for prospect response matching."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


STOPWORDS = {
    "le",
    "la",
    "les",
    "de",
    "du",
    "des",
    "un",
    "une",
    "et",
    "en",
    "à",
    "a",
    "vous",
    "je",
    "me",
    "mon",
    "ma",
    "mes",
    "est",
    "ce",
    "c",
    "c'est",
    "pour",
    "que",
    "qui",
    "dans",
    "sur",
    "avec",
    "pas",
    "oui",
    "non",
    "d'accord",
    "madame",
    "monsieur",
    "s'il",
    "plaît",
    "svp",
}


@dataclass(frozen=True)
class DialoguePair:
    """One agent line followed by the prospect reply in a real call."""

    call_id: str
    turn_index: int
    agent: str
    prospect: str


class DialogueLibrary:
    """Indexes AssemblyAI call dialogues for prospect reply suggestions."""

    def __init__(self, transcripts_dir: Path | str) -> None:
        self.transcripts_dir = Path(transcripts_dir)
        self.pairs = self._load_pairs()
        self.prospect_lines = self._unique_prospect_lines()

    def best_prospect_reply(self, agent_message: str, turn: int) -> str | None:
        """Return the closest prospect reply from real calls."""
        reply, _score = self.best_prospect_reply_scored(agent_message, turn)
        return reply

    def best_prospect_reply_scored(self, agent_message: str, turn: int) -> tuple[str | None, float]:
        """Return the best real reply and its confidence score."""
        ranked = self.rank_prospect_replies(agent_message, turn, limit=1)
        if not ranked:
            return None, 0.0
        return ranked[0]

    def find_prospect_replies(self, agent_message: str, turn: int, limit: int = 5) -> list[str]:
        """Rank real prospect replies for the current agent message."""
        return [reply for reply, _score in self.rank_prospect_replies(agent_message, turn, limit)]

    def rank_prospect_replies(
        self, agent_message: str, turn: int, limit: int = 5
    ) -> list[tuple[str, float]]:
        """Rank real prospect replies with confidence scores."""
        if not self.pairs:
            return []

        from engine.prospect_coherence import detect_agent_intents, is_coherent_reply

        agent_tokens = _tokenize(agent_message)
        agent_intents = detect_agent_intents(agent_message)
        scored: list[tuple[float, str]] = []

        for pair in self.pairs:
            overlap = _token_overlap(agent_tokens, _tokenize(pair.agent))
            turn_bonus = max(0.0, 1.0 - abs(pair.turn_index - turn) * 0.08)
            intent_bonus = _intent_overlap(agent_intents, detect_agent_intents(pair.agent))
            score = overlap * 2.2 + turn_bonus + intent_bonus

            if not is_coherent_reply(agent_message, pair.prospect):
                score *= 0.15

            if overlap > 0 or intent_bonus > 0.4 or abs(pair.turn_index - turn) <= 2:
                scored.append((score, pair.prospect))

        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[tuple[str, float]] = []
        seen: set[str] = set()
        for score, prospect in scored:
            key = prospect.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            results.append((prospect, score))
            if len(results) >= limit:
                break
        return results

    def format_for_prompt(self, agent_message: str, turn: int, limit: int = 4) -> str:
        """Format real call examples for the LLM system prompt."""
        if not self.pairs:
            return "Aucun dialogue réel chargé."

        matches = self.find_prospect_replies(agent_message, turn, limit=limit)
        if not matches:
            sample = self.prospect_lines[:limit]
            lines = [f"- {line}" for line in sample]
            return (
                "Répliques prospect issues de vrais appels (AssemblyAI):\n"
                + "\n".join(lines)
            )

        blocks: list[str] = []
        for prospect in matches:
            for pair in self.pairs:
                if pair.prospect == prospect:
                    blocks.append(f"Agent: {pair.agent}\nProspect: {pair.prospect}")
                    break
        return (
            "Exemples réels (agent → prospect) tirés des appels transcrits:\n\n"
            + "\n\n".join(blocks)
        )

    def _load_pairs(self) -> list[DialoguePair]:
        pairs: list[DialoguePair] = []
        for path in sorted(self.transcripts_dir.glob("*_dialogue.json")):
            try:
                with path.open("r", encoding="utf-8") as file:
                    payload = json.load(file)
            except (json.JSONDecodeError, OSError):
                continue

            turns = payload.get("turns", [])
            if not turns:
                continue

            call_id = path.stem.replace("_dialogue", "")
            prospect_turn = 0
            for index, turn in enumerate(turns):
                if turn.get("role") != "agent":
                    continue
                if index + 1 >= len(turns):
                    continue
                next_turn = turns[index + 1]
                if next_turn.get("role") != "prospect":
                    continue
                agent_text = str(turn.get("text", "")).strip()
                prospect_text = str(next_turn.get("text", "")).strip()
                if not agent_text or not prospect_text:
                    continue
                prospect_turn += 1
                pairs.append(
                    DialoguePair(
                        call_id=call_id,
                        turn_index=prospect_turn,
                        agent=agent_text,
                        prospect=prospect_text,
                    )
                )
        return pairs

    def token_overlap_score(self, left_text: str, right_text: str) -> float:
        return _token_overlap_score(left_text, right_text)

    def _unique_prospect_lines(self) -> list[str]:
        seen: set[str] = set()
        lines: list[str] = []
        for pair in self.pairs:
            key = pair.prospect.lower().strip()
            if key in seen:
                continue
            seen.add(key)
            lines.append(pair.prospect)
        return lines


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zàâäéèêëïîôùûüç0-9']+", text.lower())
    return {word for word in words if len(word) > 2 and word not in STOPWORDS}


def _token_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left), 1)


def _token_overlap_score(left_text: str, right_text: str) -> float:
    return _token_overlap(_tokenize(left_text), _tokenize(right_text))


def _intent_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    shared = left & right
    if not shared:
        return 0.0
    return min(1.2, len(shared) * 0.45)
