"""Automatic call evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from engine.knowledge import KnowledgeBase


@dataclass(frozen=True)
class EvaluationResult:
    """Structured evaluation output for the UI."""

    scores: dict[str, int]
    final_score: int
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]


class Evaluator:
    """Evaluates trainee behavior using call history and KB expectations."""

    CATEGORIES = (
        "Introduction",
        "Ton professionnel",
        "Traitement des objections",
        "Écoute",
        "Logique commerciale",
        "Contrôle de l'appel",
        "Conclusion",
    )

    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.knowledge_base = knowledge_base

    def evaluate(
        self,
        history: list[dict[str, str]],
        profile: str,
        difficulty: str,
    ) -> EvaluationResult:
        """Score the conversation and generate coaching feedback."""
        trainee_turns = [item["content"] for item in history if item["role"] == "trainee"]
        full_text = " ".join(trainee_turns).lower()
        expected_answers = " ".join(
            self.knowledge_base.expected_answers_for_context(profile, difficulty)
        ).lower()

        scores = {
            "Introduction": self._score_keywords(full_text, ("bonjour", "nom", "appelle", "raison", "rapidement"), 5),
            "Ton professionnel": self._score_professional_tone(trainee_turns),
            "Traitement des objections": self._score_overlap(full_text, expected_answers),
            "Écoute": self._score_keywords(full_text, ("comprends", "entends", "inquiétude", "question", "clair"), 5),
            "Logique commerciale": self._score_keywords(full_text, ("facture", "prix", "économie", "avantage", "comparer", "tarif"), 5),
            "Contrôle de l'appel": self._score_keywords(full_text, ("puis-je", "question", "rapidement", "vérifier", "instant"), 5),
            "Conclusion": self._score_keywords(full_text, ("rendez-vous", "envoyer", "rappeler", "suite", "disponible"), 5),
        }
        final_score = round((sum(scores.values()) / (len(scores) * 10)) * 100)
        strengths = self._strengths(scores)
        weaknesses = self._weaknesses(scores)
        suggestions = self._suggestions(scores, difficulty)
        return EvaluationResult(scores, final_score, strengths, weaknesses, suggestions)

    @staticmethod
    def _score_keywords(text: str, keywords: tuple[str, ...], target_hits: int) -> int:
        hits = sum(1 for keyword in keywords if keyword in text)
        return max(1, min(10, round((hits / target_hits) * 10)))

    @staticmethod
    def _score_professional_tone(turns: list[str]) -> int:
        if not turns:
            return 1
        text = " ".join(turns).lower()
        score = 7
        if any(term in text for term in ("please", "thank", "appreciate")):
            score += 2
        if any(term in text for term in ("obviously", "listen to me", "you need to", "wrong")):
            score -= 4
        avg_words = sum(len(turn.split()) for turn in turns) / len(turns)
        if avg_words > 110:
            score -= 2
        return max(1, min(10, score))

    @staticmethod
    def _score_overlap(text: str, expected_answers: str) -> int:
        if not text:
            return 1
        expected_terms = {
            word.strip(".,;:!?()")
            for word in expected_answers.split()
            if len(word.strip(".,;:!?()")) > 5
        }
        trainee_terms = {
            word.strip(".,;:!?()")
            for word in text.split()
            if len(word.strip(".,;:!?()")) > 5
        }
        if not expected_terms:
            return 5
        overlap = len(expected_terms & trainee_terms)
        return max(1, min(10, round((overlap / min(len(expected_terms), 18)) * 10)))

    @staticmethod
    def _strengths(scores: dict[str, int]) -> list[str]:
        strong = [name for name, score in scores.items() if score >= 8]
        if strong:
            return [f"Bon niveau sur: {name.lower()}." for name in strong[:3]]
        return ["Vous avez maintenu l'échange et terminé la simulation."]

    @staticmethod
    def _weaknesses(scores: dict[str, int]) -> list[str]:
        weak = [name for name, score in scores.items() if score <= 5]
        if weak:
            return [f"À travailler: {name.lower()}." for name in weak[:3]]
        return ["Pas de faiblesse majeure détectée, mais l'appel peut encore être plus précis."]

    @staticmethod
    def _suggestions(scores: dict[str, int], difficulty: str) -> list[str]:
        suggestions = []
        if scores["Écoute"] < 7:
            suggestions.append("Reformulez l'inquiétude du client avant de présenter un bénéfice.")
        if scores["Traitement des objections"] < 7:
            suggestions.append("Répondez à chaque objection avec preuve, réassurance et concision.")
        if scores["Conclusion"] < 7:
            suggestions.append("Terminez avec une prochaine étape claire: rappel, envoi ou rendez-vous.")
        if difficulty.lower() == "advanced":
            suggestions.append("En niveau avancé, gardez des réponses courtes et reprenez le contrôle par des questions calmes.")
        return suggestions or ["Gardez la structure: écouter, clarifier, répondre, confirmer, conclure."]
