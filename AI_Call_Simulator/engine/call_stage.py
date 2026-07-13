"""Detect which phase of an outbound energy sales call the agent is in."""

from __future__ import annotations

import re
import unicodedata


STAGE_ORDER = (
    "greeting",
    "identity",
    "mail_tariff",
    "provider",
    "billing_amount",
    "billing_mode",
    "bill_satisfaction",
    "kwh_price",
    "comparatif",
    "address",
    "email",
    "personal_info",
    "housing",
    "offer",
    "objection",
    "validation",
    "closing",
)


STAGE_PATTERNS: dict[str, tuple[str, ...]] = {
    "mail_tariff": (
        r"mail.*augmentation",
        r"augmentation.*tarif",
        r"reçu.*mail",
        r"recu.*mail",
        r"reçu.*email",
        r"mail.*fournisseur",
        r"notification.*tarif",
        r"hausse.*tarif",
        r"augmentation.*facture",
    ),
    "identity": (
        r"c'est vous qui gérez",
        r"c'est bien vous",
        r"je vous ai",
        r"je parle bien",
        r"c'est bien monsieur",
        r"c'est bien madame",
    ),
    "provider": (
        r"quel fournisseur",
        r"quelle fournisseur",
        r"chez quel fournisseur",
        r"fournisseur actuel",
        r"vous êtes chez",
        r"vous etiez chez",
    ),
    "billing_amount": (
        r"combien.*par mois",
        r"combien vous payez",
        r"combien chez",
        r"mensualit",
        r"montant.*facture",
    ),
    "billing_mode": (
        r"prix fixe ou réel",
        r"mensualité fixe",
        r"ce que vous consommez",
        r"facturation.*fixe",
        r"payez.*réel",
    ),
    "bill_satisfaction": (
        r"pas content",
        r"pas satisfait",
        r"content de.*payer",
        r"content de.*facture",
        r"satisfait.*facture",
        r"payez.*cher",
        r"trop cher",
        r"augmente.*facture",
        r"facture.*augment",
        r"mécontent",
        r"insatisfait",
    ),
    "kwh_price": (
        r"prix du kilowatt",
        r"prix du kwh",
        r"kilowatt.heure",
        r"centimes.*kwh",
        r"€.*kwh",
    ),
    "comparatif": (
        r"lancer un comparatif",
        r"faire un comparatif",
        r"comparatif",
        r"comparer",
        r"5 minutes",
    ),
    "address": (
        r"votre adresse",
        r"code postal",
        r"rue ",
        r"donner votre adresse",
        r"localise",
    ),
    "email": (
        r"adresse mail",
        r"adresse e-mail",
        r"adresse email",
        r"@gmail",
        r"boîte mail",
        r"boite mail",
    ),
    "personal_info": (
        r"date de naissance",
        r"nom c'est",
        r"prénom",
        r"prenom",
        r"confirmer.*nom",
    ),
    "housing": (
        r"appartement",
        r"maison",
        r"propriétaire",
        r"locataire",
        r"combien de personnes",
        r"chauffage",
        r"gaz",
        r"radiateur",
        r"voiture électrique",
    ),
    "offer": (
        r"offre",
        r"home energy",
        r"homme énergie",
        r"prix du kwh fixe",
        r"heures creuses",
        r"heures pleines",
        r"abonnement compteur",
        r"mensualité.*€",
    ),
    "objection": (
        r"intéresse pas",
        r"interesse pas",
        r"pas le temps",
        r"arnaque",
        r"méfiant",
        r"change.*fournisseur",
    ),
    "validation": (
        r"code de 4 chiffres",
        r"valider votre contrat",
        r"confirmer.*contrat",
        r"autorisez.*enregistrer",
        r"rétractation",
        r"raccrocher.*rappeler",
    ),
    "closing": (
        r"bonne journée",
        r"au revoir",
        r"merci.*madame",
        r"merci.*monsieur",
    ),
    "greeting": (
        r"^bonjour",
        r"je suis .* de",
        r"je vous contacte",
        r"concernant vos factures",
        r"concernant votre facture",
    ),
}


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).lower().strip()
    value = value.replace("'", "'").replace("`", "'")
    value = re.sub(r"\s+", " ", value)
    return value


def extract_focus_phrase(agent_message: str) -> str:
    """Return the most question-like part of a long agent pitch."""
    text = agent_message.strip()
    if not text:
        return text

    chunks = re.split(r"(?<=[.!?])\s+", text)
    question_chunks = [
        chunk
        for chunk in chunks
        if "?" in chunk
        or re.search(
            r"\b(je voulais savoir|savoir si|est-ce que|avez-vous|pouvez-vous|combien|quel|quelle)\b",
            chunk.lower(),
        )
    ]
    if question_chunks:
        return question_chunks[-1].strip()

    for chunk in reversed(chunks):
        if len(chunk.split()) >= 4:
            return chunk.strip()
    return text


def detect_call_stage(agent_message: str) -> str:
    """Infer the call stage from the agent's latest utterance."""
    text = normalize_text(agent_message)
    focus = normalize_text(extract_focus_phrase(agent_message))

    scores: dict[str, int] = {}
    for stage, patterns in STAGE_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, focus):
                score += 3
            elif re.search(pattern, text):
                score += 1
        if score:
            scores[stage] = score

    if not scores:
        return "greeting"

    # Prefer specific stages over generic greeting when multiple match
    if "greeting" in scores and len(scores) > 1:
        del scores["greeting"]

    best_stage = max(scores, key=lambda key: (scores[key], -STAGE_ORDER.index(key)))
    return best_stage
