"""Conversation orchestration for the outbound sales call simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.call_models import CallModelLibrary
from engine.customer_state import CustomerState
from engine.dialogue_library import DialogueLibrary
from engine.knowledge import KnowledgeBase
from engine.llm import OllamaClient
from engine.prompt_builder import PromptBuilder
from engine.prospect_facts import ProspectFacts, create_prospect_facts
from engine.prospect_responder import ProspectResponder


@dataclass
class ConversationEngine:
    """Manages state, memory, prompting, and LLM calls for one simulated call."""

    profile: str
    difficulty: str
    knowledge_base: KnowledgeBase
    call_models: CallModelLibrary
    dialogue_library: DialogueLibrary
    llm_client: OllamaClient = field(default_factory=OllamaClient)
    prompt_builder: PromptBuilder = field(default_factory=PromptBuilder)
    use_llm: bool = False
    state: CustomerState = field(init=False)
    prospect_facts: ProspectFacts = field(init=False)
    history: list[dict[str, str]] = field(default_factory=list)
    ended: bool = False
    last_reply_meta: dict[str, Any] = field(default_factory=dict)
    responder: ProspectResponder = field(init=False)

    def __post_init__(self) -> None:
        self.state = CustomerState.create(self.profile, self.difficulty)
        self.prospect_facts = create_prospect_facts(self.profile, self.difficulty)
        self.responder = ProspectResponder(
            profile=self.profile,
            difficulty=self.difficulty,
            knowledge_base=self.knowledge_base,
            call_models=self.call_models,
            dialogue_library=self.dialogue_library,
            llm_client=self.llm_client,
            prompt_builder=self.prompt_builder,
            prospect_facts=self.prospect_facts,
            use_llm=self.use_llm,
        )

    @classmethod
    def from_paths(
        cls,
        profile: str,
        difficulty: str,
        knowledge_base_path: Path | str,
        call_models_path: Path | str,
        transcripts_dir: Path | str,
        model: str = "qwen2.5:7b",
        ollama_url: str = "http://localhost:11434",
        use_llm: bool = False,
    ) -> "ConversationEngine":
        """Create an engine from application config paths."""
        return cls(
            profile=profile,
            difficulty=difficulty,
            knowledge_base=KnowledgeBase(knowledge_base_path),
            call_models=CallModelLibrary(call_models_path),
            dialogue_library=DialogueLibrary(transcripts_dir),
            llm_client=OllamaClient(model=model, base_url=ollama_url),
            use_llm=use_llm,
        )

    def start(self) -> None:
        """Start the call. The sales agent speaks first on outbound calls."""
        if self.history:
            return

    def respond_to_trainee(self, trainee_response: str) -> str:
        """Persist trainee input, update state, and return the customer response."""
        if self.ended:
            return "The call has already ended."
        clean_response = trainee_response.strip()
        if not clean_response:
            raise ValueError("Trainee response cannot be empty.")

        self._append("trainee", clean_response)
        self.state.update_after_trainee_response(clean_response)
        previous_customer = [item["content"] for item in self.history if item["role"] == "customer"]
        objection = self.knowledge_base.find_relevant(
            profile=self.profile,
            difficulty=self.difficulty,
            turn=self.state.conversation_turn,
        )

        result = self.responder.reply(
            agent_message=clean_response,
            state=self.state,
            history=self.history,
            objection=objection,
            previous_customer_lines=previous_customer,
        )
        reply = result.text
        self.last_reply_meta = {
            "stage": result.stage,
            "source": result.source,
            "confidence": round(result.confidence, 2),
            "provider": self.prospect_facts.provider,
            "question": result.question_label,
            "tenure": f"{self.prospect_facts.provider_since_years} ans",
        }

        if self.state.should_hang_up():
            self.ended = True
        self._append("customer", reply)
        return reply

    def end(self) -> None:
        """Mark the current conversation as ended."""
        self.ended = True

    def _append(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
