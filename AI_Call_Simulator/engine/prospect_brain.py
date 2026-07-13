"""Deterministic prospect brain: classify agent question → profile-aware answer."""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.knowledge import normalize_profile
from engine.prospect_facts import ProspectFacts


@dataclass(frozen=True)
class QuestionMatch:
    kind: str
    label: str


QUESTION_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "mail_received",
        "Mail d'augmentation reçu ?",
        (
            r"reçu.*mail",
            r"recu.*mail",
            r"mail.*augmentation",
            r"augmentation.*tarif",
            r"mail.*fournisseur",
            r"reçu.*email",
            r"avez.*reçu.*mail",
        ),
    ),
    (
        "provider_tenure",
        "Depuis combien de temps chez le fournisseur ?",
        (
            r"depuis combien",
            r"depuis quand",
            r"ça fait combien",
            r"ca fait combien",
            r"depuis combien de temps",
            r"combien de temps",
            r"combien de temps.*chez",
            r"combien de temps que",
            r"fait combien.*chez",
        ),
    ),
    (
        "provider",
        "Quel fournisseur ?",
        (
            r"quel fournisseur",
            r"quelle fournisseur",
            r"chez qui",
            r"fournisseur actuel",
            r"vous êtes chez quel",
            r"êtes chez quel",
            r"^edf\s*,?\s*(?:et|vous|c'est)",
            r"^engie\s*,",
            r"^total",
        ),
    ),
    (
        "billing_amount",
        "Montant facture ?",
        (
            r"combien.*par mois",
            r"combien vous payez",
            r"mensualit",
        ),
    ),
    (
        "billing_mode",
        "Réel ou fixe ?",
        (
            r"fixe ou réel",
            r"réel ou fixe",
            r"ce que vous consommez",
            r"mensualité fixe",
        ),
    ),
    (
        "bill_satisfaction",
        "Satisfait des factures ?",
        (
            r"pas content",
            r"content de.*payer",
            r"content de.*facture",
            r"satisfait",
            r"trop cher",
        ),
    ),
    (
        "kwh_price",
        "Prix du kWh ?",
        (r"prix du kwh", r"kilowatt", r"centimes.*kwh"),
    ),
    (
        "comparatif",
        "Comparatif ?",
        (r"comparatif", r"comparer", r"5 minutes"),
    ),
    (
        "identity",
        "Identité / qui gère ?",
        (
            r"c'est vous qui gérez",
            r"c'est bien vous",
            r"je parle bien",
            r"c'est bien monsieur",
            r"c'est bien madame",
        ),
    ),
    (
        "greeting",
        "Accroche",
        (
            r"^bonjour",
            r"je suis .* de",
            r"je vous contacte",
        ),
    ),
)


def classify_question(agent_message: str, turn: int) -> QuestionMatch:
    text = _norm(agent_message)
    focus = _norm(_focus(agent_message))

    for kind, label, patterns in QUESTION_RULES:
        if kind == "greeting" and turn > 1:
            continue
        for pattern in patterns:
            if re.search(pattern, focus) or re.search(pattern, text):
                return QuestionMatch(kind=kind, label=label)

    return QuestionMatch(kind="unknown", label="Autre")


def answer_question(
    agent_message: str,
    profile: str,
    difficulty: str,
    facts: ProspectFacts,
    turn: int,
) -> tuple[str, QuestionMatch]:
    """Return the prospect answer and the detected question type."""
    match = classify_question(agent_message, turn)
    profile_key = normalize_profile(profile)
    diff = difficulty.lower()

    answer = _answer_for_kind(match.kind, profile_key, diff, facts, turn, agent_message)
    return answer, match


def _answer_for_kind(
    kind: str,
    profile: str,
    diff: str,
    facts: ProspectFacts,
    turn: int,
    agent_message: str,
) -> str:
    if kind == "mail_received":
        return _mail_answer(profile, diff, facts)
    if kind == "provider_tenure":
        return _tenure_answer(profile, diff, facts)
    if kind == "provider":
        return _provider_answer(profile, diff, facts)
    if kind == "billing_amount":
        return _amount_answer(profile, diff, facts)
    if kind == "billing_mode":
        return facts.billing_mode.rstrip(".") + "."
    if kind == "bill_satisfaction":
        return _satisfaction_answer(profile, diff)
    if kind == "kwh_price":
        return _kwh_answer(profile, diff, facts)
    if kind == "comparatif":
        return _comparatif_answer(profile, diff)
    if kind == "identity":
        return _identity_answer(profile)
    if kind == "greeting" and turn <= 1:
        return _greeting_answer(profile, agent_message)
    return _generic_answer(profile, diff)


def _mail_answer(profile: str, diff: str, facts: ProspectFacts) -> str:
    if not facts.mail_received:
        if profile == "suspicious customer":
            return "Non, je ne l'ai pas vu."
        if diff == "advanced":
            return "Non, pas à ma connaissance."
        return "Non, je ne l'ai pas reçu."
    if not facts.mail_read:
        if profile == "curious customer":
            return "Oui je crois, mais je n'ai pas encore regardé. C'est quoi l'augmentation ?"
        return "Oui, je l'ai reçu, mais je n'ai pas encore ouvert le mail."
    if profile == "aggressive customer":
        return "Oui, j'ai reçu le mail, et oui ça augmente."
    if profile == "curious customer":
        return "Oui, je l'ai reçu. Vous savez combien ça représente ?"
    return "Oui, je l'ai bien reçu."


def _tenure_answer(profile: str, diff: str, facts: ProspectFacts) -> str:
    years = facts.provider_since_years
    provider = facts.provider
    base = f"Ça fait {years} ans chez {provider}."
    if profile == "busy customer":
        return f"{years} ans, je crois."
    if profile == "well-informed customer":
        return f"Depuis {years} ans environ, chez {provider}."
    if profile == "suspicious customer" and diff != "beginner":
        return f"Pourquoi ? Ça fait {years} ans."
    return base


def _provider_answer(profile: str, diff: str, facts: ProspectFacts) -> str:
    provider = facts.provider
    if profile == "suspicious customer" and diff != "beginner":
        return f"{provider}, oui. Pourquoi vous me demandez ça ?"
    if profile == "well-informed customer":
        return f"Je suis chez {provider}."
    return f"{provider}."


def _amount_answer(profile: str, diff: str, facts: ProspectFacts) -> str:
    if profile == "busy customer":
        return "Euh… je sais pas de tête, ça dépend des mois."
    if diff == "advanced" and profile == "aggressive customer":
        return "Pourquoi, vous allez me faire une offre ?"
    return facts.monthly_bill.rstrip(".") + "."


def _satisfaction_answer(profile: str, diff: str) -> str:
    answers = {
        "busy customer": "Franchement non, ça monte et j'ai pas le temps.",
        "aggressive customer": "Non, c'est beaucoup trop cher.",
        "suspicious customer": "Pas vraiment. Vous pouvez faire quoi concrètement ?",
        "curious customer": "Pas vraiment — vous pouvez m'aider à payer moins ?",
        "well-informed customer": "Non, je trouve que je paye déjà cher.",
    }
    default = "Pas vraiment, les factures augmentent."
    answer = answers.get(profile, default)
    if diff == "beginner" and profile == "aggressive customer":
        return "Non, pas trop."
    return answer


def _kwh_answer(profile: str, diff: str, facts: ProspectFacts) -> str:
    if facts.kwh_awareness:
        return "Je crois autour de 0,20 € le kWh."
    return "Non, je ne connais pas le tarif au kWh."


def _comparatif_answer(profile: str, diff: str) -> str:
    answers = {
        "busy customer": "D'accord, mais faites vite.",
        "aggressive customer": "Non merci." if diff == "advanced" else "Bon, allez-y, mais vite.",
        "suspicious customer": "C'est sans engagement ?",
        "curious customer": "Oui, on peut regarder.",
        "well-informed customer": "D'accord, montrez-moi les chiffres.",
    }
    return answers.get(profile, "D'accord, on peut regarder.")


def _identity_answer(profile: str) -> str:
    answers = {
        "busy customer": "Oui, c'est moi qui gère.",
        "aggressive customer": "Oui, c'est moi. Qu'est-ce que vous voulez ?",
        "suspicious customer": "Oui… qui êtes-vous exactement ?",
    }
    return answers.get(profile, "Oui, c'est bien moi.")


def _greeting_answer(profile: str, agent_message: str) -> str:
    if "mail" in _norm(agent_message) or "augmentation" in _norm(agent_message):
        return _mail_answer(profile, "intermediate", _facts_from_greeting_only())
    answers = {
        "busy customer": "Oui bonjour, mais faites vite.",
        "aggressive customer": "Oui, qu'est-ce que c'est ?",
        "suspicious customer": "Bonjour. Pourquoi vous m'appelez ?",
        "curious customer": "Oui bonjour, je vous écoute.",
        "well-informed customer": "Oui bonjour.",
    }
    return answers.get(profile, "Oui bonjour.")


def _generic_answer(profile: str, diff: str) -> str:
    if profile == "busy customer":
        return "D'accord, mais allez droit au but."
    if profile == "aggressive customer":
        return "Oui, et alors ?"
    return "D'accord, je vous écoute."


def _facts_from_greeting_only() -> ProspectFacts:
    from engine.prospect_facts import create_prospect_facts

    return create_prospect_facts("curious customer", "intermediate")


def _norm(text: str) -> str:
    value = text.lower().strip()
    value = value.replace("'", "'")
    return re.sub(r"\s+", " ", value)


def _focus(agent_message: str) -> str:
    chunks = re.split(r"(?<=[.!?])\s+", agent_message.strip())
    for chunk in reversed(chunks):
        if "?" in chunk or re.search(r"\b(depuis|combien|reçu|est-ce que|avez-vous)\b", chunk.lower()):
            return chunk.strip()
    return chunks[-1].strip() if chunks else agent_message
