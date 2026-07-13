"""Knowledge-base loading and objection retrieval."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROFILE_ALIASES = {
    "aggressive customer": "aggressive customer",
    "agressif": "aggressive customer",
    "client agressif": "aggressive customer",
    "busy customer": "busy customer",
    "client pressé": "busy customer",
    "pressé": "busy customer",
    "suspicious customer": "suspicious customer",
    "méfiant": "suspicious customer",
    "client méfiant": "suspicious customer",
    "curious customer": "curious customer",
    "curieux": "curious customer",
    "curieux / hésitant": "curious customer",
    "client curieux": "curious customer",
    "well-informed customer": "well-informed customer",
    "well informed customer": "well-informed customer",
    "client bien informé": "well-informed customer",
    "bien informé": "well-informed customer",
}

DIFFICULTY_ALIASES = {
    "beginner": "beginner",
    "débutant": "beginner",
    "intermediate": "intermediate",
    "intermédiaire": "intermediate",
    "advanced": "advanced",
    "avancé": "advanced",
}


@dataclass(frozen=True)
class Objection:
    """A sales objection and the expected handling guidance."""

    profile: str
    difficulty: str
    objection: str
    expected_answer: str
    easy_reaction: str = ""
    intermediate_reaction: str = ""
    difficult_reaction: str = ""
    emotional_evolution: str = ""


class KnowledgeBase:
    """Loads and filters objection guidance from JSON."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._objections = self._load()

    @property
    def objections(self) -> list[Objection]:
        """Return all objections."""
        return list(self._objections)

    def find_relevant(self, profile: str, difficulty: str, turn: int) -> Objection:
        """Select a relevant objection for the current profile and call turn."""
        normalized_profile = normalize_profile(profile)
        normalized_difficulty = normalize_difficulty(difficulty)

        exact = [
            item
            for item in self._objections
            if normalize_profile(item.profile) == normalized_profile
            and normalize_difficulty(item.difficulty) == normalized_difficulty
        ]
        profile_matches = [
            item for item in self._objections if normalize_profile(item.profile) == normalized_profile
        ]
        candidates = exact or profile_matches or self._objections
        if not candidates:
            raise ValueError("The knowledge base does not contain any objections.")
        return candidates[turn % len(candidates)]

    def reply_to_agent_message(
        self,
        agent_message: str,
        profile: str,
        difficulty: str,
        patience: int,
        trust: int,
    ) -> str | None:
        """Pick a KB reaction when the agent message matches a known theme."""
        text = agent_message.lower()
        theme_keywords = {
            "mail": ("mail", "email", "e-mail", "courrier", "boîte mail", "boite mail"),
            "tariff_increase": ("augmentation", "tarif", "tarifs", "augmenté"),
            "provider": ("fournisseur", "chez qui", "quel fournisseur"),
            "amount": ("combien", "payez", "facture", "mensualit"),
            "interest": ("intéresse", "interesse", "intérêt"),
            "time": ("temps", "occupé", "occupée", "pressé", "pressée"),
            "scam": ("arnaque", "méfiant", "confiance"),
        }

        matched_themes: set[str] = set()
        for theme, keywords in theme_keywords.items():
            if any(keyword in text for keyword in keywords):
                matched_themes.add(theme)

        if not matched_themes:
            return None

        normalized_profile = normalize_profile(profile)
        normalized_difficulty = normalize_difficulty(difficulty)
        candidates = [
            item
            for item in self._objections
            if normalize_profile(item.profile) == normalized_profile
            and normalize_difficulty(item.difficulty) == normalized_difficulty
        ] or [
            item for item in self._objections if normalize_profile(item.profile) == normalized_profile
        ]

        best: Objection | None = None
        best_score = 0
        for item in candidates:
            blob = " ".join(
                (
                    item.objection,
                    item.easy_reaction,
                    item.intermediate_reaction,
                    item.difficult_reaction,
                )
            ).lower()
            score = 0
            if "mail" in matched_themes and any(word in blob for word in ("mail", "reçu", "email")):
                score += 3
            if "tariff_increase" in matched_themes and any(
                word in blob for word in ("augmentation", "tarif", "facture")
            ):
                score += 2
            if "provider" in matched_themes and "fournisseur" in blob:
                score += 2
            if "amount" in matched_themes and any(word in blob for word in ("facture", "payez", "combien")):
                score += 2
            if "interest" in matched_themes and "intéresse" in blob:
                score += 2
            if "time" in matched_themes and any(word in blob for word in ("temps", "occupé", "pressé")):
                score += 2
            if "scam" in matched_themes and any(word in blob for word in ("arnaque", "méfiant", "confiance")):
                score += 2
            if score > best_score:
                best = item
                best_score = score

        if not best or best_score == 0:
            return None

        if patience >= 60 and trust >= 55:
            return best.easy_reaction or None
        if patience >= 35 and trust >= 35:
            return best.intermediate_reaction or None
        return best.difficult_reaction or None

    def pick_reaction_for_state(self, profile: str, difficulty: str, turn: int, patience: int, trust: int) -> str:
        """Return a short French customer line from the knowledge base without calling the LLM."""
        objection = self.find_relevant(profile, difficulty, turn)
        if patience >= 60 and trust >= 55:
            return objection.easy_reaction or "D'accord, je vous écoute."
        if patience >= 35 and trust >= 35:
            return objection.intermediate_reaction or objection.objection
        return objection.difficult_reaction or objection.objection

    def expected_answers_for_context(self, profile: str, difficulty: str) -> list[str]:
        """Return expected answers used by the evaluator as a rubric."""
        normalized_profile = normalize_profile(profile)
        normalized_difficulty = normalize_difficulty(difficulty)
        matches = [
            item.expected_answer
            for item in self._objections
            if normalize_profile(item.profile) == normalized_profile
            and normalize_difficulty(item.difficulty) in {
                normalized_difficulty,
                "beginner",
                "intermediate",
                "advanced",
            }
        ]
        return matches or [item.expected_answer for item in self._objections]

    def _load(self) -> list[Objection]:
        if not self.path.exists():
            raise FileNotFoundError(f"Knowledge base not found: {self.path}")
        with self.path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        items = raw.get("objections", raw if isinstance(raw, list) else [])
        objections: list[Objection] = []
        for item in items:
            record: dict[str, Any] = dict(item)
            objections.append(
                Objection(
                    profile=str(record["profile"]),
                    difficulty=str(record["difficulty"]),
                    objection=_clean_text(str(record["objection"])),
                    expected_answer=_clean_text(str(record["expected_answer"])),
                    easy_reaction=_clean_text(str(record.get("easy_reaction", ""))),
                    intermediate_reaction=_clean_text(
                        str(record.get("intermediate_reaction", record.get("medium_reaction", "")))
                    ),
                    difficult_reaction=_clean_text(
                        str(record.get("difficult_reaction", record.get("hard_reaction", "")))
                    ),
                    emotional_evolution=_clean_text(
                        str(record.get("emotional_evolution", record.get("emotion", "")))
                    ),
                )
            )
        return objections


def normalize_profile(value: str) -> str:
    key = value.strip().lower()
    return PROFILE_ALIASES.get(key, key)


def normalize_difficulty(value: str) -> str:
    key = value.strip().lower()
    return DIFFICULTY_ALIASES.get(key, key)


def _clean_text(value: str) -> str:
    cleaned = re.sub(r"\s*•\s*", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
