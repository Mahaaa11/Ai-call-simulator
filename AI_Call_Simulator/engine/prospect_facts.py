"""Consistent fictional facts for each simulated prospect."""

from __future__ import annotations

import random
from dataclasses import dataclass

from engine.knowledge import normalize_profile


PROVIDERS = ("EDF", "Engie", "TotalEnergies", "Alpiq", "Ekwateur", "Mint Énergie")
BILLING_MODES = ("Je paye au réel, selon ma consommation.", "J'ai une mensualité fixe.")


@dataclass(frozen=True)
class ProspectFacts:
    provider: str
    monthly_bill: str
    mail_received: bool
    mail_read: bool
    billing_mode: str
    kwh_awareness: bool
    provider_since_years: int = 3

    def to_prompt_block(self) -> str:
        mail_status = (
            "Oui, mail reçu et lu."
            if self.mail_received and self.mail_read
            else "Oui, mail reçu mais pas encore lu."
            if self.mail_received
            else "Non, pas reçu ou pas vu."
        )
        kwh = "Connaît son tarif kWh." if self.kwh_awareness else "Ne connaît pas son tarif kWh."
        return (
            "Vos faits (restez cohérent tout l'appel):\n"
            f"- Fournisseur actuel: {self.provider} (depuis {self.provider_since_years} ans)\n"
            f"- Facture mensuelle: {self.monthly_bill}\n"
            f"- Mail augmentation: {mail_status}\n"
            f"- Facturation: {self.billing_mode}\n"
            f"- {kwh}"
        )


def create_prospect_facts(profile: str, difficulty: str, seed: int = 0) -> ProspectFacts:
    rng = random.Random(f"{normalize_profile(profile)}:{difficulty}:{seed}")
    diff = difficulty.lower()

    mail_received = diff == "beginner" or (diff == "intermediate" and rng.random() > 0.35)
    mail_read = mail_received and (diff == "beginner" or rng.random() > 0.45)
    kwh_aware = normalize_profile(profile) == "well-informed customer" or (
        diff == "beginner" and rng.random() > 0.7
    )

    bill_ranges = {
        "beginner": (65, 130),
        "intermediate": (80, 160),
        "advanced": (95, 185),
    }
    low, high = bill_ranges.get(diff, bill_ranges["intermediate"])
    amount = rng.randint(low, high)
    tenure = rng.randint(1, 8)

    return ProspectFacts(
        provider=rng.choice(PROVIDERS),
        monthly_bill=f"Environ {amount} € par mois.",
        mail_received=mail_received,
        mail_read=mail_read,
        billing_mode=rng.choice(BILLING_MODES),
        kwh_awareness=kwh_aware,
        provider_since_years=tenure,
    )
