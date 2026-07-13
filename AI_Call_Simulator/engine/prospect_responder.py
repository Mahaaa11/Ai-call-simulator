"""Prospect replies via deterministic brain; optional LLM paraphrase."""

from __future__ import annotations

from dataclasses import dataclass

from engine.call_models import CallModelLibrary
from engine.customer_state import CustomerState
from engine.dialogue_library import DialogueLibrary
from engine.knowledge import KnowledgeBase, Objection
from engine.llm import LLMError, OllamaClient
from engine.prompt_builder import PromptBuilder
from engine.prospect_brain import answer_question, classify_question
from engine.prospect_coherence import is_coherent_reply, is_identity_reply
from engine.prospect_facts import ProspectFacts


@dataclass
class ProspectReply:
    text: str
    source: str
    stage: str
    confidence: float
    question_label: str = ""


class ProspectResponder:
    """Answer the agent's question using profile + facts. LLM optional paraphrase only."""

    def __init__(
        self,
        profile: str,
        difficulty: str,
        knowledge_base: KnowledgeBase,
        call_models: CallModelLibrary,
        dialogue_library: DialogueLibrary,
        llm_client: OllamaClient,
        prompt_builder: PromptBuilder,
        prospect_facts: ProspectFacts,
        *,
        use_llm: bool = False,
    ) -> None:
        self.profile = profile
        self.difficulty = difficulty
        self.knowledge_base = knowledge_base
        self.call_models = call_models
        self.dialogue_library = dialogue_library
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self.prospect_facts = prospect_facts
        self.use_llm = use_llm

    def reply(
        self,
        agent_message: str,
        state: CustomerState,
        history: list[dict[str, str]],
        objection: Objection,
        previous_customer_lines: list[str],
    ) -> ProspectReply:
        turn = state.conversation_turn
        answer, match = answer_question(
            agent_message,
            self.profile,
            self.difficulty,
            self.prospect_facts,
            turn,
        )

        if self.use_llm:
            paraphrased = self._maybe_paraphrase(
                agent_message, answer, match.kind, state, history, objection
            )
            if paraphrased and self._valid(agent_message, paraphrased, match.kind, turn, previous_customer_lines):
                return ProspectReply(
                    paraphrased,
                    "llm_paraphrase",
                    match.kind,
                    0.9,
                    match.label,
                )

        if not self._valid(agent_message, answer, match.kind, turn, previous_customer_lines):
            answer, match = answer_question(agent_message, self.profile, self.difficulty, self.prospect_facts, turn)

        return ProspectReply(answer, "brain", match.kind, 0.95, match.label)

    def _maybe_paraphrase(
        self,
        agent_message: str,
        base_answer: str,
        kind: str,
        state: CustomerState,
        history: list[dict[str, str]],
        objection: Objection,
    ) -> str | None:
        call_model_text = self.call_models.format_for_prompt(
            self.profile, state.conversation_turn, state.patience, state.trust
        )
        system = (
            self.prompt_builder.build_system_prompt(
                state,
                objection,
                history,
                call_model_text,
                f"Réponse correcte à garder: {base_answer}",
                [item["content"] for item in history if item["role"] == "customer"],
                self.prospect_facts,
                agent_message,
                kind,
            )
            + "\n\nReformule légèrement la réponse correcte ci-dessus. Ne change PAS le sens. 1 phrase max."
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": agent_message}]
        try:
            return self.llm_client.chat(messages).strip()
        except LLMError:
            return None

    def _valid(
        self,
        agent_message: str,
        reply: str,
        kind: str,
        turn: int,
        previous: list[str],
    ) -> bool:
        clean = reply.strip()
        if not clean:
            return False
        if clean.lower() in {line.lower().strip() for line in previous}:
            return False
        if is_identity_reply(clean) and kind not in {"identity", "greeting"}:
            return False
        if kind != "greeting" and turn > 1 and clean.lower().startswith(("oui bonjour", "bonjour")):
            return False
        if not is_coherent_reply(agent_message, clean):
            return False
        return True
