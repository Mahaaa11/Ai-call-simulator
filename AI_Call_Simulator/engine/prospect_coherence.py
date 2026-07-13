"""Validate that prospect replies match what the agent actually asked."""

from __future__ import annotations

import re
import unicodedata


IDENTITY_REPLY_PATTERNS = (
    r"^oui[\s,]*c['']est (?:bien )?moi",
    r"^c['']est (?:bien )?moi",
    r"^oui[\s,]*c['']est moi qui gère",
)

SATISFACTION_PATTERNS = (
    r"pas content",
    r"pas satisfait",
    r"content de.*payer",
    r"content de.*facture",
    r"satisfait",
    r"trop cher",
    r"payez.*cher",
)

IDENTITY_PATTERNS = (
    r"c'est bien vous",
    r"je vous ai",
    r"vous m'avez",
    r"je parle bien",
    r"c'est vous qui gérez",
    r"c'est bien monsieur",
    r"c'est bien madame",
)

MAIL_PATTERNS = (
    r"mail",
    r"e-mail",
    r"email",
    r"courrier",
    r"boîte mail",
    r"boite mail",
)

TARIFF_PATTERNS = (
    r"augmentation",
    r"tarif",
    r"tarifs",
    r"facture",
    r"factures",
)

PROVIDER_PATTERNS = (
    r"quel fournisseur",
    r"quelle fournisseur",
    r"chez qui",
    r"fournisseur actuel",
    r"vous êtes chez",
    r"vous etiez chez",
)

AMOUNT_PATTERNS = (
    r"combien vous payez",
    r"combien par mois",
    r"montant",
    r"mensualit",
)

QUESTION_PATTERNS = (
    r"\?",
    r"\best-ce que\b",
    r"\bavez-vous\b",
    r"\bpouvez-vous\b",
    r"\bvoulez-vous\b",
    r"\bsouhaitez-vous\b",
    r"\bje voulais savoir\b",
    r"\bsavoir si\b",
    r"\bbien reçu\b",
    r"\bbien recu\b",
    r"\bavez reçu\b",
    r"\bavez recu\b",
)

GENERIC_PERFECT_RE = re.compile(
    r"^(?:oh\s+)?oui[\s,]*c['']est parfait\.?$|^c['']est parfait\.?$",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Lowercase and normalize apostrophes for stable matching."""
    value = unicodedata.normalize("NFKC", text).lower().strip()
    value = value.replace("’", "'").replace("`", "'")
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .!?")


def is_generic_perfect(reply: str) -> bool:
    return bool(GENERIC_PERFECT_RE.match(normalize_text(reply)))


def detect_agent_intents(agent_message: str) -> set[str]:
    """Return coarse intents inferred from the agent's last line."""
    text = normalize_text(agent_message)
    intents: set[str] = set()

    if any(re.search(pattern, text) for pattern in QUESTION_PATTERNS):
        intents.add("question")

    if any(re.search(pattern, text) for pattern in IDENTITY_PATTERNS):
        intents.add("identity")

    if any(re.search(pattern, text) for pattern in MAIL_PATTERNS):
        intents.add("mail")

    if any(re.search(pattern, text) for pattern in TARIFF_PATTERNS):
        intents.add("tariff")

    if any(re.search(pattern, text) for pattern in PROVIDER_PATTERNS):
        intents.add("provider")

    if any(re.search(pattern, text) for pattern in AMOUNT_PATTERNS):
        intents.add("amount")

    if any(re.search(pattern, text) for pattern in SATISFACTION_PATTERNS):
        intents.add("satisfaction")

    if re.search(r"\b(comparatif|comparer|proposer une offre)\b", text):
        intents.add("comparatif")

    if re.search(r"\b(reçu|recu|reçue|recue)\b", text) and ("mail" in intents or "tariff" in intents):
        intents.add("receipt_check")

    return intents


def is_coherent_reply(agent_message: str, prospect_reply: str) -> bool:
    """Reject generic lines that do not answer the agent's question."""
    agent = agent_message.strip()
    reply = prospect_reply.strip()
    if not agent or not reply:
        return False

    intents = detect_agent_intents(agent)
    normalized = normalize_text(reply)

    if is_generic_perfect(reply):
        if "identity" in intents:
            return True
        return False

    if any(re.search(pattern, normalized) for pattern in IDENTITY_REPLY_PATTERNS):
        if "identity" not in intents:
            return False

    if "c'est parfait" in normalized and not ("identity" in intents or "comparatif" in intents):
        return False

    if "mail" in intents or "receipt_check" in intents:
        mail_words = ("mail", "email", "reçu", "recu", "vu", "ouvert", "regard", "spam", "courrier")
        provider_names = ("edf", "engie", "total", "alpiq", "ekwateur", "mint")
        if any(name in normalized for name in provider_names):
            if not any(word in normalized for word in ("mail", "email", "reçu", "recu", "courrier")):
                return False
        yes_no = ("oui", "non", "pas encore", "je sais pas", "je ne sais pas", "pas reçu", "pas recu", "pas vu")
        if not any(word in normalized for word in mail_words + yes_no):
            return False

    if "satisfaction" in intents:
        satisfaction_words = (
            "oui",
            "non",
            "cher",
            "augment",
            "content",
            "satisfait",
            "pas content",
            "trop",
            "facture",
            "aide",
            "réduire",
            "reduire",
        )
        if not any(word in normalized for word in satisfaction_words):
            return False

    if "tariff" in intents and ("question" in intents or "receipt_check" in intents):
        if normalized in {"oui", "d'accord", "ok"} or is_generic_perfect(reply):
            return False

    if "provider" in intents:
        if normalized in {"oui", "d'accord", "ok"} or is_generic_perfect(reply):
            return False

    if "amount" in intents and "question" in intents:
        if normalized in {"oui", "d'accord", "ok"} or "parfait" in normalized:
            return False

    return True


def is_identity_reply(reply: str) -> bool:
    normalized = normalize_text(reply)
    return any(re.search(pattern, normalized) for pattern in IDENTITY_REPLY_PATTERNS)


def contextual_fallback(agent_message: str, difficulty: str) -> str | None:
    """Return a scripted prospect line when intents are clear but retrieval failed."""
    intents = detect_agent_intents(agent_message)
    text = normalize_text(agent_message)
    diff = difficulty.strip().lower()

    if "mail" in intents or "receipt_check" in intents:
        if diff in {"advanced", "avancé"}:
            return "Non, je ne l'ai pas encore reçu."
        if diff in {"intermediate", "intermédiaire"}:
            return "Oui je crois, mais je n'ai pas encore regardé."
        return "Oui, je l'ai reçu de mon fournisseur."

    if "tariff" in intents and ("question" in intents or "augmentation" in text):
        if diff in {"advanced", "avancé"}:
            return "Oui, j'ai vu une hausse, ça m'inquiète un peu."
        if diff in {"intermediate", "intermédiaire"}:
            return "Oui, j'ai remarqué que ça a augmenté."
        return "Oui, mes factures ont un peu augmenté."

    if "identity" in intents:
        return "Oui, c'est bien moi."

    if "satisfaction" in intents:
        if diff in {"advanced", "avancé"}:
            return "Non, franchement ça augmente trop."
        if diff in {"intermediate", "intermédiaire"}:
            return "Pas vraiment, oui ça monte."
        return "Oui un peu, les factures augmentent."

    if "provider" in intents:
        return "EDF."

    if "amount" in intents and "question" in intents:
        return "Je ne sais pas exactement, ça dépend des mois."

    return None


def finalize_prospect_reply(agent_message: str, reply: str, difficulty: str) -> str:
    """Last gate: never return an incoherent or generic-perfect line."""
    clean = reply.strip()
    if clean and is_coherent_reply(agent_message, clean):
        return clean

    fallback = contextual_fallback(agent_message, difficulty)
    if fallback:
        return fallback

    intents = detect_agent_intents(agent_message)
    if "mail" in intents or "receipt_check" in intents:
        return "Oui, je l'ai reçu."
    if "tariff" in intents:
        return "Oui, j'ai remarqué une augmentation."
    if "provider" in intents:
        return "EDF."
    return "D'accord, je vous écoute."
