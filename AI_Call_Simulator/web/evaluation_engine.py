"""Heuristic evaluation engine for simulator conversations (server-side re-eval)."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


EVAL_GRID = [
    {
        "section": "1. Accroche et prise de contact",
        "max": 15,
        "items": [
            {"name": "Présentation claire (nom, entreprise, objet de l'appel)", "max": 5},
            {"name": "Accroche efficace et engageante", "max": 5},
            {"name": "Ton professionnel et dynamique", "max": 3},
            {"name": "Respect du temps client", "max": 2},
        ],
    },
    {
        "section": "2. Découverte des besoins",
        "max": 20,
        "items": [
            {"name": "Questions ouvertes et pertinentes", "max": 6},
            {"name": "Écoute active (pas d'interruption)", "max": 5},
            {"name": "Reformulation des besoins", "max": 4},
            {"name": "Identification des freins et motivations", "max": 5},
        ],
    },
    {
        "section": "3. Argumentation commerciale",
        "max": 20,
        "items": [
            {"name": "Adaptation au discours client", "max": 6},
            {"name": "Mise en avant des bénéfices", "max": 6},
            {"name": "Structuration claire des arguments", "max": 4},
            {"name": "Maîtrise du produit", "max": 4},
        ],
    },
    {
        "section": "4. Gestion des objections",
        "max": 15,
        "items": [
            {"name": "Écoute sans confrontation", "max": 4},
            {"name": "Réponses adaptées et argumentées", "max": 5},
            {"name": "Transformation des objections en opportunités", "max": 4},
            {"name": "Ton calme et professionnel", "max": 2},
        ],
    },
    {
        "section": "5. Closing",
        "max": 15,
        "items": [
            {"name": "Proposition claire", "max": 5},
            {"name": "Technique de closing naturelle", "max": 5},
            {"name": "Obtention d'un engagement", "max": 5},
        ],
    },
    {
        "section": "6. Communication et attitude",
        "max": 10,
        "items": [
            {"name": "Ton de voix (énergie, assurance)", "max": 4},
            {"name": "Clarté du langage", "max": 3},
            {"name": "Empathie et relationnel", "max": 3},
        ],
    },
    {
        "section": "7. Organisation de l'appel",
        "max": 5,
        "items": [
            {"name": "Respect de la structure", "max": 3},
            {"name": "Fluidité globale", "max": 2},
        ],
    },
]

NUMBER_ASK_RE = re.compile(
    r"comment avez-vous eu mon num|comment vous avez mon num|d'où.*numéro|"
    r"pourquoi.*m'appelez|pourquoi cet appel|bloctel|eu mon num|eu mes données|"
    r"comment avez-vous eu mes",
    re.I,
)
BAD_NUMBER_REPLY_RE = re.compile(
    r"base de donn|base de contact|fichier client|notre base|listing|on a une base|database|"
    r"fichier nominatif|fichier de client|nos bases|base client",
    re.I,
)
EVASIVE_NUMBER_REPLY_RE = re.compile(
    r"je n'en sais rien|je n'ai aucune idée|aucune idée|pas nominatif|"
    r"numéro qui s'affiche|numero qui s'affiche|je sais pas d'où|"
    r"appels ne sont pas nominatifs|pote numéro",
    re.I,
)
GOOD_NUMBER_REPLY_RE = re.compile(
    r"consentement|formulaire|demande en ligne|partenaire|enedis|grdf|"
    r"vous nous avez contact|laissé vos coordonnées|opt.?in|base légale|"
    r"intérêt légitime|comparateur gratuit|demande de comparatif|"
    r"vous avez demandé|inscription|rgpd",
    re.I,
)


def _clamp(n: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, n))


def _level_label(score: int) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Bon"
    if score >= 50:
        return "À améliorer"
    return "Coaching nécessaire"


def _ignored_number_origin(messages: list[dict]) -> tuple[bool, str]:
    """Prospect asks origin of number; next agent reply does not address it."""
    for i, msg in enumerate(messages):
        if msg.get("speaker") != "prospect":
            continue
        if not NUMBER_ASK_RE.search(msg.get("content", "")):
            continue
        for j in range(i + 1, len(messages)):
            if messages[j].get("speaker") != "agent":
                continue
            reply = messages[j].get("content", "")
            if BAD_NUMBER_REPLY_RE.search(reply):
                return False, ""
            if GOOD_NUMBER_REPLY_RE.search(reply):
                return False, ""
            return True, reply[:120]
        break
    return False, ""


def analyze_compliance(
    agent_msgs: list[str],
    prospect_msgs: list[str],
    *,
    ordered_messages: list[dict] | None = None,
) -> dict[str, Any]:
    agent_text = " ".join(agent_msgs)
    prospect_text = " ".join(prospect_msgs)
    agent_lower = agent_text.lower()
    prospect_lower = prospect_text.lower()

    prospect_asked_number = bool(NUMBER_ASK_RE.search(prospect_lower))
    bad_number_msgs = [m[:160] for m in agent_msgs if BAD_NUMBER_REPLY_RE.search(m)]
    evasive_number_msgs = [m[:160] for m in agent_msgs if EVASIVE_NUMBER_REPLY_RE.search(m)]
    good_number_reply = bool(GOOD_NUMBER_REPLY_RE.search(agent_lower))

    bad_database_reply = prospect_asked_number and bool(bad_number_msgs)
    evasive_number_reply = prospect_asked_number and bool(evasive_number_msgs) and not good_number_reply
    ignored_number_reply = False
    ignored_number_example = ""
    if (
        ordered_messages
        and prospect_asked_number
        and not bad_database_reply
        and not good_number_reply
        and not evasive_number_reply
    ):
        ignored_number_reply, ignored_number_example = _ignored_number_origin(ordered_messages)

    reformulated = bool(re.search(r"je comprends|je vous comprends", agent_lower))
    has_economy = bool(re.search(r"20\s*€|économ|moins cher|\d+\s*€", agent_lower))
    has_comparatif = "comparatif" in agent_lower
    has_empathy = bool(re.search(r"je comprends|madame|monsieur|rassure", agent_lower))
    has_intro = bool(re.search(r"bonjour|je suis|génie|genie|comparateur", agent_lower))
    has_discovery = bool(re.search(r"fournisseur|engie|edf|combien|payez|électricit", agent_lower))
    has_offer_price = bool(re.search(r"20\s*€|économ|moins cher", agent_lower))
    agent_frustration = bool(re.search(r"ne voulez pas faire des économies|si vous ne voulez pas", agent_lower))
    call_lost = bool(re.search(r"au revoir", prospect_lower[-200:])) and not re.search(
        r"iban|fr\d{2}|on peut avancer|prochaine étape", agent_lower + prospect_lower
    )
    prospect_yielded = bool(
        re.search(
            r"on peut avancer|prochaine étape|d'accord.*comparatif|bon.*convaincu|"
            r"on regarde le comparatif",
            prospect_lower,
        )
    )

    objection_handling = 0
    for i, pmsg in enumerate(prospect_msgs):
        if not re.search(
            r"changer|fournisseur|intéresse pas|numéro|numero|iban|résiliation|confiance|"
            r"engie|mail|bloctel|compliqu",
            pmsg,
            re.I,
        ):
            continue
        if i >= len(agent_msgs):
            continue
        amsg = agent_msgs[i] if i < len(agent_msgs) else ""
        ref = bool(re.search(r"je comprends|je vous comprends|tout à fait|rassure", amsg, re.I))
        concrete = bool(
            re.search(
                r"comparatif|gratuit|sans engagement|économ|€|résiliation|génie|genie|moins cher",
                amsg,
                re.I,
            )
        )
        if (ref and concrete) or (concrete and len(amsg) >= 70):
            objection_handling += 1

    penalty = 0
    bonus = 0
    axes: list[str] = []
    points_forts: list[str] = []

    if bad_database_reply:
        penalty += 18
        axes.append(
            "Erreur majeure : ne jamais évoquer une « base de données » ou « fichier clients » "
            "quand le prospect demande l'origine de son numéro — utiliser consentement, "
            "formulaire web, partenaire ou demande de comparatif."
        )
    elif evasive_number_reply or ignored_number_reply:
        penalty += 10
        if ignored_number_reply:
            axes.append(
                "Question ignorée sur l'origine du numéro : ne pas enchaîner sur un autre sujet "
                "(gaz/électricité, PDL…) — répondre clairement (consentement, comparateur, partenaire)."
            )
        else:
            axes.append(
                "Réponse insuffisante sur l'origine du numéro : éviter « je ne sais pas » ou "
                "« numéro affiché » — expliquer le cadre (consentement, comparateur, partenaire)."
            )
    elif prospect_asked_number and good_number_reply:
        bonus += 4
        points_forts.append("Bonne réponse sur l'origine du contact (consentement / cadre légal).")

    if reformulated and objection_handling >= 3:
        bonus += 6
        points_forts.append("Reformulation et écoute des objections du prospect.")
    if has_economy:
        bonus += 3
        points_forts.append("Arguments chiffrés (économies) communiqués.")
    if prospect_yielded:
        bonus += 5
    if agent_frustration:
        penalty += 8
        axes.append("Ne pas conclure par la frustration — rester professionnel.")
    if call_lost and objection_handling >= 3 and not prospect_yielded:
        penalty += 5
        axes.append("Ne pas abandonner trop tôt après avoir traité les objections.")

    while len(axes) < 3:
        axes.append("Reformuler le refus client avant de relancer.")
    while len(points_forts) < 2:
        points_forts.append("Analyse basée sur la transcription réelle de l'appel.")

    return {
        "prospect_asked_number": prospect_asked_number,
        "bad_database_reply": bad_database_reply,
        "bad_number_examples": bad_number_msgs[:2],
        "evasive_number_reply": evasive_number_reply,
        "evasive_number_examples": evasive_number_msgs[:2],
        "ignored_number_reply": ignored_number_reply,
        "ignored_number_example": ignored_number_example,
        "good_number_reply": good_number_reply,
        "reformulated": reformulated,
        "objection_handling": objection_handling,
        "prospect_yielded": prospect_yielded,
        "has_intro": has_intro,
        "has_discovery": has_discovery,
        "has_comparatif": has_comparatif,
        "has_offer_price": has_offer_price,
        "has_empathy": has_empathy,
        "agent_frustration": agent_frustration,
        "call_lost": call_lost,
        "penalty": penalty,
        "bonus": bonus,
        "axes_amelioration": axes[:3],
        "points_forts": points_forts[:3],
    }


def _score_items(items: list[dict], scores: list[int], comments: list[str]) -> list[dict]:
    out = []
    for i, item in enumerate(items):
        mx = item["max"]
        sc = _clamp(scores[i] if i < len(scores) else mx // 2, 0, mx)
        out.append(
            {
                "name": item["name"],
                "score": sc,
                "max": mx,
                "comment": comments[i] if i < len(comments) else "—",
            }
        )
    return out


def compute_heuristic_evaluation(messages: list[dict]) -> dict[str, Any]:
    agent_msgs = [m.get("content", "") for m in messages if m.get("speaker") == "agent"]
    prospect_msgs = [m.get("content", "") for m in messages if m.get("speaker") == "prospect"]
    sig = analyze_compliance(agent_msgs, prospect_msgs, ordered_messages=messages)
    full = " ".join(agent_msgs).lower()
    questions = full.count("?")

    number_comment = "—"
    if sig["bad_database_reply"]:
        ex = sig["bad_number_examples"][0] if sig["bad_number_examples"] else ""
        number_comment = f"Interdit : mention « base de données » / fichier — « {ex[:90]}… »"
    elif sig["evasive_number_reply"]:
        ex = sig["evasive_number_examples"][0] if sig["evasive_number_examples"] else ""
        number_comment = f"Réponse évasive sur l'origine du numéro — « {ex[:90]}… »"
    elif sig.get("ignored_number_reply"):
        ex = sig.get("ignored_number_example") or ""
        number_comment = f"Question ignorée sur l'origine du numéro — relance : « {ex[:90]}… »"
    elif sig["prospect_asked_number"] and sig["good_number_reply"]:
        number_comment = "Origine du numéro expliquée correctement (consentement / cadre)."

    obj_resp_score = 2
    if sig["bad_database_reply"]:
        obj_resp_score = 0
    elif sig["evasive_number_reply"] or sig.get("ignored_number_reply"):
        obj_resp_score = 1
    elif sig["objection_handling"] >= 4:
        obj_resp_score = 4
    elif sig["objection_handling"] >= 2:
        obj_resp_score = 3

    sections_raw = [
        (
            EVAL_GRID[0],
            [
                4 if sig["has_intro"] else 2,
                3 if sig["has_intro"] else 2,
                1 if sig["agent_frustration"] else 2,
                2,
            ],
            [
                "Présentation Génie / comparateur repérée." if sig["has_intro"] else "Présentation incomplète.",
                "Objet facture / comparatif annoncé.",
                "Ton hésitant." if not sig["has_empathy"] else "Ton professionnel.",
                "Durée acceptable.",
            ],
        ),
        (
            EVAL_GRID[1],
            [
                4 if sig["has_discovery"] else 2,
                2 if sig["objection_handling"] >= 2 else 1,
                2 if sig["reformulated"] else 1,
                3 if sig["prospect_asked_number"] else 3,
            ],
            [
                "Découverte fournisseur / facture.",
                "Écoute des réponses prospect.",
                "Reformulation partielle." if sig["reformulated"] else "Peu de reformulation.",
                "Freins identifiés (changement fournisseur, origine appel)." if sig["prospect_asked_number"] else "Freins partiellement identifiés.",
            ],
        ),
        (
            EVAL_GRID[2],
            [
                3 if sig["has_comparatif"] else 2,
                3 if sig["has_offer_price"] else 1,
                2 if sig["has_comparatif"] else 1,
                2,
            ],
            [
                "Comparatif et indépendance vis-à-vis du fournisseur.",
                "Bénéfices chiffrés." if sig["has_offer_price"] else "Peu de chiffres concrets.",
                "Structure perfectible.",
                "Maîtrise produit moyenne.",
            ],
        ),
        (
            EVAL_GRID[3],
            [
                2 if sig["agent_frustration"] else 3,
                obj_resp_score,
                2 if sig["prospect_yielded"] else 1,
                0 if sig["agent_frustration"] else 2,
            ],
            [
                "Écoute globalement correcte." if not sig["agent_frustration"] else "Perte de calme.",
                number_comment if sig["prospect_asked_number"] else (
                    "Réponses aux objections perfectibles."
                    if sig["objection_handling"] < 3
                    else "Bonnes réponses argumentées aux objections."
                ),
                "Peu de transformation." if sig["call_lost"] and not sig["prospect_yielded"] else "Relance closing.",
                "Ton calme." if not sig["agent_frustration"] else "Frustration en fin d'appel.",
            ],
        ),
        (
            EVAL_GRID[4],
            [3 if sig["has_comparatif"] else 2, 2, 4 if sig["prospect_yielded"] else (1 if sig["call_lost"] else 2)],
            [
                "Proposition comparatif.",
                "Closing perfectible.",
                "Engagement obtenu." if sig["prospect_yielded"] else "Pas d'engagement final.",
            ],
        ),
        (
            EVAL_GRID[5],
            [2, 1, 2 if sig["has_empathy"] else 1],
            ["Énergie moyenne.", "Phrases parfois longues.", "Empathie présente." if sig["has_empathy"] else "Peu d'empathie."],
        ),
        (
            EVAL_GRID[6],
            [2, 1 if not sig["call_lost"] else 0],
            ["Structure accroche → découverte → comparatif.", "Fluidité moyenne."],
        ),
    ]

    sections = []
    for grid, scores, comments in sections_raw:
        items = _score_items(grid["items"], scores, comments)
        sections.append(
            {
                "name": grid["section"],
                "max": grid["max"],
                "score": sum(i["score"] for i in items),
                "items": items,
            }
        )

    score_total = _clamp(sum(s["score"] for s in sections) + sig["bonus"] - sig["penalty"])

    reco = []
    if sig["bad_database_reply"] or sig["evasive_number_reply"] or sig.get("ignored_number_reply"):
        reco.append(
            "Script origine numéro : « Vous avez laissé vos coordonnées via notre comparateur / "
            "un formulaire partenaire — jamais « base de données ». »"
        )
    reco.append("Reformuler chaque objection avant de relancer le comparatif.")
    if sig["call_lost"]:
        reco.append("Ne pas raccrocher tant que le prospect n'a pas eu de réponses claires sur ses freins.")

    return {
        "score_total": score_total,
        "niveau": _level_label(score_total),
        "sections": sections,
        "points_forts": sig["points_forts"],
        "axes_amelioration": sig["axes_amelioration"],
        "recommandations": reco[:3],
        "_source": "heuristic_v2",
        "_compliance": {
            "bad_database_reply": sig["bad_database_reply"],
            "evasive_number_reply": sig["evasive_number_reply"],
            "ignored_number_reply": sig.get("ignored_number_reply"),
            "objection_handling": sig["objection_handling"],
            "prospect_yielded": sig["prospect_yielded"],
        },
    }


def reevaluate_from_messages(messages: list[dict], previous: dict | None = None) -> dict[str, Any]:
    """Compute fresh evaluation; preserve exam_meta from previous if present."""
    ev = compute_heuristic_evaluation(messages)
    if previous and isinstance(previous, dict):
        if previous.get("exam_meta"):
            ev["exam_meta"] = deepcopy(previous["exam_meta"])
    ev["_reevaluated"] = True
    return ev
