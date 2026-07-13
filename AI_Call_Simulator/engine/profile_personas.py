"""Profile-specific prospect behavior for prompts and rule-based replies."""

from __future__ import annotations

from engine.knowledge import normalize_profile

PROFILE_PERSONAS: dict[str, dict[str, str]] = {
    "busy customer": {
        "label": "Client pressé",
        "tone": "Impatient, réponses très courtes (5-12 mots max). Veut aller vite.",
        "style": "« Allez-y vite », « J'ai une minute », « Oui / Non » direct.",
        "objection_style": "Rappelle le manque de temps, menace de raccrocher.",
    },
    "aggressive customer": {
        "label": "Client agressif",
        "tone": "Hostile, sceptique dès le départ, ton sec.",
        "style": "Challenge l'agent, refuse facilement, peut être brusque.",
        "objection_style": "« Encore un appel commercial », « Laissez-moi tranquille ».",
    },
    "suspicious customer": {
        "label": "Client méfiant",
        "tone": "Méfiant, demande des explications avant de coopérer.",
        "style": "Pose des questions de vérification (qui êtes-vous, pourquoi vous appelez).",
        "objection_style": "Peur arnaque, protection des données personnelles.",
    },
    "curious customer": {
        "label": "Client curieux",
        "tone": "Ouvert mais exigeant, pose des questions de clarification.",
        "style": "Écoute si c'est concret, compare, veut comprendre l'intérêt.",
        "objection_style": "« Expliquez-moi concrètement », « Quelle différence avec mon offre ? ».",
    },
    "well-informed customer": {
        "label": "Client bien informé",
        "tone": "Connaît le marché, compare les tarifs, exige des chiffres.",
        "style": "Mentionne son fournisseur/tarif actuel, challenge les arguments vagues.",
        "objection_style": "« J'ai déjà comparé », « Montrez-moi le kWh ».",
    },
}

DIFFICULTY_MODIFIERS: dict[str, str] = {
    "beginner": "Coopératif modéré — répond aux questions sans trop résister.",
    "intermediate": "Réservé — hésite, pose des questions, ne donne pas tout de suite.",
    "advanced": "Difficile — résiste, objecte, peut refuser ou menacer de raccrocher.",
}


def persona_for_profile(profile: str) -> dict[str, str]:
    return PROFILE_PERSONAS.get(normalize_profile(profile), PROFILE_PERSONAS["curious customer"])


def difficulty_modifier(difficulty: str) -> str:
    key = difficulty.strip().lower()
    return DIFFICULTY_MODIFIERS.get(key, DIFFICULTY_MODIFIERS["intermediate"])


def format_persona_block(profile: str, difficulty: str) -> str:
    persona = persona_for_profile(profile)
    return (
        f"Profil prospect: {persona['label']}\n"
        f"Ton: {persona['tone']}\n"
        f"Style oral: {persona['style']}\n"
        f"Objections typiques: {persona['objection_style']}\n"
        f"Niveau difficulté: {difficulty_modifier(difficulty)}"
    )
