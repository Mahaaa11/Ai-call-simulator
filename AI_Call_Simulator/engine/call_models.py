"""Complete call models per customer profile."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from engine.knowledge import normalize_profile


@dataclass(frozen=True)
class CallStage:
    """One stage in a profile call script."""

    id: str
    label: str
    turn: int
    customer_examples: tuple[str, ...]
    good_agent: str
    neutral_agent: str
    bad_agent: str


@dataclass(frozen=True)
class ProfileCallModel:
    """Full outbound call script for one prospect profile."""

    profile: str
    name: str
    stages: tuple[CallStage, ...]


class CallModelLibrary:
    """Loads and serves profile-specific call scripts."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._models = self._load()

    def get_model(self, profile: str) -> ProfileCallModel | None:
        return self._models.get(normalize_profile(profile))

    def get_stage(self, profile: str, turn: int) -> CallStage | None:
        model = self.get_model(profile)
        if not model:
            return None
        for stage in model.stages:
            if stage.turn == turn:
                return stage
        return model.stages[-1] if model.stages else None

    def get_stage_by_id(self, profile: str, stage_id: str) -> CallStage | None:
        model = self.get_model(profile)
        if not model:
            return None
        for stage in model.stages:
            if stage.id == stage_id:
                return stage
        return None

    def pick_stage_response(self, profile: str, turn: int, patience: int, trust: int) -> str:
        """Pick a scripted customer line for the current call stage."""
        stage = self.get_stage(profile, turn)
        if not stage:
            return "D'accord."

        if patience >= 60 and trust >= 55:
            return stage.good_agent
        if patience >= 35 and trust >= 35:
            return stage.neutral_agent
        return stage.bad_agent

    def format_for_prompt(self, profile: str, turn: int, patience: int, trust: int) -> str:
        """Format the full call model context for the LLM."""
        model = self.get_model(profile)
        if not model:
            return "No call model loaded for this profile."

        stage = self.get_stage(profile, turn)
        if not stage:
            return "No call stage found."

        suggested = self.pick_stage_response(profile, turn, patience, trust)
        examples = "\n".join(f"  - {line}" for line in stage.customer_examples)
        upcoming = []
        for item in model.stages:
            if item.turn > turn:
                upcoming.append(f"  Tour {item.turn} ({item.label}): ex. {item.customer_examples[0]}")
            if len(upcoming) >= 3:
                break

        upcoming_text = "\n".join(upcoming) if upcoming else "  Fin de l'appel proche."

        return f"""
Modèle d'appel complet — profil « {model.name} »
Étape actuelle: Tour {stage.turn} — {stage.label}
Réponse suggérée selon l'état du prospect: {suggested}

Exemples réels de répliques prospect à cette étape:
{examples}

Prochaines étapes typiques de l'appel:
{upcoming_text}

Règle: répondez comme dans un VRAI appel de vente d'énergie — court, naturel, réactif.
Ne posez PAS de questions comme un commercial. Vous êtes le CLIENT, pas l'agent.
""".strip()

    def _load(self) -> dict[str, ProfileCallModel]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as file:
            raw = json.load(file)

        models: dict[str, ProfileCallModel] = {}
        for profile_key, payload in raw.get("models", {}).items():
            stages = tuple(
                CallStage(
                    id=str(stage["id"]),
                    label=str(stage["label"]),
                    turn=int(stage["turn"]),
                    customer_examples=tuple(str(item) for item in stage.get("customer_examples", [])),
                    good_agent=str(stage.get("good_agent", "D'accord.")),
                    neutral_agent=str(stage.get("neutral_agent", "D'accord.")),
                    bad_agent=str(stage.get("bad_agent", "Non merci.")),
                )
                for stage in payload.get("stages", [])
            )
            models[normalize_profile(profile_key)] = ProfileCallModel(
                profile=profile_key,
                name=str(payload.get("name", profile_key)),
                stages=stages,
            )
        return models
