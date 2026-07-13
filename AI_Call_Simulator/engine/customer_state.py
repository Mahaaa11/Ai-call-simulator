"""Customer state model and deterministic state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CustomerState:
    """Tracks the simulated prospect's evolving mood and call posture."""

    profile: str
    difficulty: str
    patience: int
    trust: int
    interest: int
    emotion: str
    conversation_turn: int = 0

    @classmethod
    def create(cls, profile: str, difficulty: str) -> "CustomerState":
        """Create a balanced initial state from a profile and difficulty."""
        difficulty_key = difficulty.lower()
        profile_key = profile.lower()

        base_by_difficulty = {
            "beginner": {"patience": 70, "trust": 55, "interest": 55, "emotion": "neutral"},
            "intermediate": {"patience": 55, "trust": 45, "interest": 45, "emotion": "guarded"},
            "advanced": {"patience": 40, "trust": 35, "interest": 35, "emotion": "tense"},
        }
        state = base_by_difficulty.get(difficulty_key, base_by_difficulty["intermediate"]).copy()

        profile_adjustments = {
            "busy customer": {"patience": -15, "interest": -5, "emotion": "impatient"},
            "aggressive customer": {"patience": -10, "trust": -10, "emotion": "hostile"},
            "suspicious customer": {"trust": -15, "emotion": "skeptical"},
            "curious customer": {"patience": 10, "interest": 15, "emotion": "curious"},
            "well-informed customer": {"trust": -5, "interest": 10, "emotion": "analytical"},
        }
        adjustment = profile_adjustments.get(profile_key, {})
        for field in ("patience", "trust", "interest"):
            state[field] = cls._clamp(int(state[field]) + int(adjustment.get(field, 0)))
        state["emotion"] = str(adjustment.get("emotion", state["emotion"]))

        return cls(profile=profile, difficulty=difficulty, **state)

    def update_after_trainee_response(self, trainee_response: str) -> None:
        """Update state using observable response qualities, not scripted replies."""
        text = trainee_response.strip()
        lowered = text.lower()
        word_count = len(text.split())
        self.conversation_turn += 1

        if not text:
            self.patience -= 12
            self.trust -= 8
        elif word_count <= 35:
            self.patience += 4
        elif word_count > 95:
            self.patience -= 10

        if any(
            term in lowered
            for term in (
                "understand",
                "i hear",
                "you're right",
                "makes sense",
                "je comprends",
                "je vous comprends",
                "vous avez raison",
                "c'est clair",
                "bien sûr",
            )
        ):
            self.trust += 8
            self.patience += 4

        if any(
            term in lowered
            for term in (
                "proof",
                "case study",
                "data",
                "guarantee",
                "privacy",
                "secure",
                "preuve",
                "données",
                "garantie",
                "confidentialité",
                "sécurisé",
                "protégées",
            )
        ):
            self.trust += 7

        if any(
            term in lowered
            for term in (
                "benefit",
                "save",
                "reduce",
                "increase",
                "improve",
                "value",
                "avantage",
                "économie",
                "réduire",
                "améliorer",
                "valeur",
                "facture",
                "tarif",
            )
        ):
            self.interest += 6

        if any(
            term in lowered
            for term in (
                "buy now",
                "sign today",
                "limited time",
                "you must",
                "achetez maintenant",
                "signez aujourd'hui",
                "offre limitée",
                "vous devez",
            )
        ):
            self.patience -= 8
            self.trust -= 6

        if "?" in text:
            self.interest += 3
            self.trust += 2

        if self.difficulty.lower() == "advanced":
            self.patience -= 3
            if self.conversation_turn % 3 == 0:
                self.trust -= 2

        self.patience = self._clamp(self.patience)
        self.trust = self._clamp(self.trust)
        self.interest = self._clamp(self.interest)
        self.emotion = self._derive_emotion()

    def should_hang_up(self) -> bool:
        """Return whether the customer is likely to end the call."""
        if self.conversation_turn < 2:
            return False
        return self.patience <= 12 or (self.trust <= 10 and self.interest <= 18)

    def to_prompt_dict(self) -> dict[str, Any]:
        """Serialize the state for prompt construction."""
        return {
            "profile": self.profile,
            "difficulty": self.difficulty,
            "patience": self.patience,
            "trust": self.trust,
            "interest": self.interest,
            "emotion": self.emotion,
            "conversation_turn": self.conversation_turn,
        }

    @staticmethod
    def _clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
        return max(minimum, min(maximum, value))

    def _derive_emotion(self) -> str:
        if self.should_hang_up():
            return "ready to hang up"
        if self.patience < 25:
            return "impatient"
        if self.trust < 25:
            return "suspicious"
        if self.interest > 70 and self.trust > 55:
            return "engaged"
        if self.interest > 60:
            return "curious"
        if self.profile.lower() == "aggressive customer" and self.trust < 45:
            return "hostile"
        return "guarded"
