"""Prompt construction for the simulated customer."""

from __future__ import annotations

from engine.call_stage import detect_call_stage, extract_focus_phrase
from engine.customer_state import CustomerState
from engine.knowledge import Objection
from engine.profile_personas import format_persona_block
from engine.prospect_facts import ProspectFacts


class PromptBuilder:
    """Builds prompts that keep the model in the customer role."""

    def build_system_prompt(
        self,
        state: CustomerState,
        current_objection: Objection,
        history: list[dict[str, str]],
        call_model_text: str = "",
        real_dialogue_text: str = "",
        previous_customer_lines: list[str] | None = None,
        prospect_facts: ProspectFacts | None = None,
        agent_message: str = "",
        stage: str = "",
    ) -> str:
        """Create the dynamic system prompt for the next customer reply."""
        history_text = self._format_history(history)
        state_data = state.to_prompt_dict()
        objection_text = self._format_objection_guidance(state, current_objection)
        repeat_guard = self._format_repeat_guard(previous_customer_lines or [])
        persona_text = format_persona_block(state.profile, state.difficulty)
        facts_text = prospect_facts.to_prompt_block() if prospect_facts else ""
        focus = extract_focus_phrase(agent_message) if agent_message else ""
        stage_label = stage or (detect_call_stage(agent_message) if agent_message else "greeting")

        return f"""
Tu es le PROSPECT (client français) dans un appel sortant de vente d'énergie.
Tu n'es PAS le commercial. Ne pose jamais de questions réservées à l'agent (tarif à proposer, comparatif à lancer).

MISSION: Répondre à la DERNIÈRE phrase de l'agent de façon naturelle, courte (1-2 phrases), orale.
Invente une réponse NOUVELLE adaptée à la question — ne copie pas mot pour mot les exemples.
Reste cohérent avec ton profil, ta difficulté et tes faits personnels.

{persona_text}

{facts_text}

Étape détectée de l'appel: {stage_label}
Question/focus de l'agent: {focus or agent_message or "accroche"}

État émotionnel: {state_data["emotion"]} | Patience {state_data["patience"]}/100 | Confiance {state_data["trust"]}/100 | Tour {state_data["conversation_turn"]}

{call_model_text}

Objections et réactions (knowledge base — adapte le TON, pas le rôle agent):
{objection_text}

Exemples tirés de VRAIS appels (style et contenu à imiter, sans copier):
{real_dialogue_text}

Historique:
{history_text}

{repeat_guard}

Règles:
- Réponds DIRECTEMENT à ce que l'agent vient de dire (oui/non, chiffre, fournisseur, mail…).
- Respecte le profil ({state_data["profile"]}) et la difficulté ({state_data["difficulty"]}).
- Pas de « c'est parfait » sauf confirmation d'identité.
- Ne dis jamais « c'est moi » sauf si l'agent demande si c'est bien vous / qui gère les factures.
- Si l'agent parle du mail reçu, réponds sur le mail — pas le nom du fournisseur seul.
- Si l'agent demande si vous êtes content de vos factures, répondez sur votre satisfaction — pas « c'est moi ».
- Pas de labels, pas d'explications, pas de coaching.
""".strip()

    def build_messages(
        self,
        state: CustomerState,
        current_objection: Objection,
        history: list[dict[str, str]],
        call_model_text: str = "",
        real_dialogue_text: str = "",
        prospect_facts: ProspectFacts | None = None,
        agent_message: str = "",
        stage: str = "",
    ) -> list[dict[str, str]]:
        """Build Ollama chat messages with proper multi-turn history."""
        previous_customer = [item["content"] for item in history if item["role"] == "customer"]
        system_prompt = self.build_system_prompt(
            state,
            current_objection,
            history,
            call_model_text,
            real_dialogue_text,
            previous_customer,
            prospect_facts,
            agent_message,
            stage,
        )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        for item in history[-8:]:
            if item["role"] == "trainee":
                messages.append({"role": "user", "content": item["content"]})
            elif item["role"] == "customer":
                messages.append({"role": "assistant", "content": item["content"]})

        return messages

    @staticmethod
    def pick_reaction(state: CustomerState, objection: Objection) -> str:
        if state.patience >= 60 and state.trust >= 55:
            return objection.easy_reaction or "D'accord, je vous écoute."
        if state.patience >= 35 and state.trust >= 35:
            return objection.intermediate_reaction or objection.objection
        return objection.difficult_reaction or objection.objection

    @staticmethod
    def _format_objection_guidance(state: CustomerState, current_objection: Objection) -> str:
        reaction = PromptBuilder.pick_reaction(state, current_objection)
        return (
            f"Objection thème: {current_objection.objection}\n"
            f"Réaction adaptée (ton prospect): {reaction}\n"
            f"Évolution émotionnelle: {current_objection.emotional_evolution}"
        )

    @staticmethod
    def _format_repeat_guard(previous_customer_lines: list[str]) -> str:
        if not previous_customer_lines:
            return "Première réponse du prospect dans cet appel."
        recent = previous_customer_lines[-3:]
        return "Ne PAS répéter: " + " | ".join(recent)

    @staticmethod
    def _format_history(history: list[dict[str, str]]) -> str:
        if not history:
            return "L'agent passe l'appel en premier."
        lines = []
        for item in history[-8:]:
            role = "Prospect" if item["role"] == "customer" else "Agent"
            lines.append(f"{role}: {item['content']}")
        return "\n".join(lines)
