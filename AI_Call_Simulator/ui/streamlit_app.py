"""Streamlit interface for the AI outbound call simulator."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from engine.assemblyai_transcriber import ProTranscriptionError, transcribe_agent_bytes
from engine.audio import AudioTranscriptionError, live_call_transcriber
from engine.conversation import ConversationEngine
from engine.dialogue_library import DialogueLibrary
from engine.evaluator import Evaluator
from engine.knowledge import KnowledgeBase
from engine.llm import LLMError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_PATH = DATA_DIR / "knowledge_base.json"
CALL_MODELS_PATH = DATA_DIR / "call_models.json"
PROFILES_PATH = DATA_DIR / "profiles.json"
STYLE_EXAMPLES_PATH = DATA_DIR / "real_call_style_examples.json"
TRANSCRIPTS_DIR = DATA_DIR / "call_transcripts"
REFERENCE_RECORDINGS_DIR = DATA_DIR / "reference_recordings"


def _load_env_file() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


class StreamlitCallSimulator:
    """Thin Streamlit layer around the call simulation engine."""

    def __init__(self) -> None:
        self.profiles = self._load_profiles()
        self.difficulties = {
            "Débutant": "Beginner",
            "Intermédiaire": "Intermediate",
            "Avancé": "Advanced",
        }

    def render(self) -> None:
        """Render the complete Streamlit app."""
        st.set_page_config(page_title="Simulateur d'appels sortants IA", page_icon="phone", layout="wide")
        st.title("Simulateur d'appels sortants IA")
        st.caption(
            "Entraînez-vous avec un prospect IA (Ollama). "
            "Transcription agent : AssemblyAI · réponses basées sur vrais appels + objections. "
            "Moteur v5.0 · prospect intelligent (questions + profil)"
        )

        self._ensure_session_defaults()
        selected_profile, selected_difficulty = self._render_sidebar()

        if st.session_state.get("evaluation"):
            self._render_evaluation()
            return

        left, right = st.columns([0.68, 0.32], gap="large")
        with left:
            self._render_conversation(selected_profile, selected_difficulty)
        with right:
            self._render_state_panel()

    def _render_sidebar(self) -> tuple[str, str]:
        st.sidebar.header("Configuration de l'appel")
        profile_names = [str(profile["name"]) for profile in self.profiles]
        selected_profile_name = st.sidebar.selectbox("Profil du prospect", profile_names)
        selected_difficulty_label = st.sidebar.selectbox(
            "Difficulté",
            list(self.difficulties.keys()),
            index=1,
        )

        profile_detail = next(item for item in self.profiles if item["name"] == selected_profile_name)
        st.sidebar.markdown("**Comportement du prospect**")
        for characteristic in profile_detail["characteristics"]:
            st.sidebar.write(f"- {characteristic}")

        st.session_state.voice_enabled = st.sidebar.toggle(
            "Faire parler le prospect",
            value=st.session_state.get("voice_enabled", True),
            help="Utilise la synthèse vocale du navigateur en français.",
        )

        model_options = {
            "qwen2.5:7b (recommandé)": "qwen2.5:7b",
            "qwen2.5:3b (rapide)": "qwen2.5:3b",
            "mistral:7b": "mistral:7b",
            "prospect-energie (fine-tuné)": "prospect-energie",
        }
        selected_model_label = st.sidebar.selectbox(
            "Modèle Ollama",
            list(model_options.keys()),
            index=0,
            help="Installez le modèle avec `ollama pull qwen2.5:7b`. "
            "Pour un modèle entraîné sur vos appels: `bash scripts/create_prospect_model.sh`.",
        )
        st.session_state.ollama_model = model_options[selected_model_label]

        st.session_state.use_llm = st.sidebar.toggle(
            "Paraphrase LLM (optionnel)",
            value=st.session_state.get("use_llm", False),
            help="Par défaut le prospect répond via le moteur intelligent (question → réponse profil). "
            "Activez seulement pour reformuler légèrement avec Ollama.",
        )

        self._render_reference_recordings()

        selected_profile_id = str(profile_detail["id"])
        selected_difficulty = self.difficulties[selected_difficulty_label]

        if st.sidebar.button("Démarrer l'appel", type="primary", use_container_width=True):
            self._start_conversation(selected_profile_id, selected_difficulty)

        if st.sidebar.button("Réinitialiser", use_container_width=True):
            self._reset()
        return selected_profile_id, selected_difficulty

    def _render_conversation(self, selected_profile: str, selected_difficulty: str) -> None:
        if "engine" not in st.session_state:
            st.info(
                "Choisissez un profil dans la barre latérale, puis cliquez sur "
                "`Démarrer l'appel`. Vous passerez l'appel en premier — le micro apparaîtra "
                "dès le début."
            )
            return

        st.subheader("Appel en direct")
        if not st.session_state.engine.history:
            st.info("Vous passez l'appel. Enregistrez votre présentation — le prospect répondra ensuite.")
        for index, message in enumerate(st.session_state.engine.history):
            label = "Vous" if message["role"] == "trainee" else "Prospect"
            with st.chat_message(label):
                st.write(message["content"])
                if message["role"] == "customer":
                    if st.button("Réécouter", key=f"replay_{index}"):
                        self._speak_text(message["content"], force_key=f"replay_{index}")

        self._speak_latest_customer_once()

        if st.session_state.engine.ended:
            st.warning("L'appel est terminé. Lancez l'évaluation quand vous êtes prêt.")
        else:
            self._render_agent_voice_input()

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Terminer l'appel", use_container_width=True):
                st.session_state.engine.end()
                self._evaluate()
                st.rerun()
        with col_b:
            if st.button("Évaluer maintenant", use_container_width=True):
                self._evaluate()
                st.rerun()

        st.caption(
            f"Profil: {self._profile_label(selected_profile)} | Difficulté: {self._difficulty_label(selected_difficulty)}"
        )

    def _render_state_panel(self) -> None:
        st.subheader("État du prospect")
        engine = st.session_state.get("engine")
        if not engine:
            st.write("Aucun appel actif.")
            return

        state = engine.state
        st.metric("Émotion", state.emotion.title())
        st.progress(state.patience / 100, text=f"Patience: {state.patience}/100")
        st.progress(state.trust / 100, text=f"Confiance: {state.trust}/100")
        st.progress(state.interest / 100, text=f"Intérêt: {state.interest}/100")
        st.write(f"Tours complétés: {state.conversation_turn}")
        facts = getattr(engine, "prospect_facts", None)
        if facts:
            st.markdown("**Fiche prospect (cohérente)**")
            st.write(f"- Fournisseur: {facts.provider} (depuis {facts.provider_since_years} ans)")
            st.write(f"- Facture: {facts.monthly_bill}")
            mail = "Reçu et lu" if facts.mail_received and facts.mail_read else "Reçu, pas lu" if facts.mail_received else "Non reçu"
            st.write(f"- Mail augmentation: {mail}")
        meta = getattr(engine, "last_reply_meta", {})
        if meta:
            st.caption(
                f"Question: **{meta.get('question', meta.get('stage', '?'))}** · "
                f"source: {meta.get('source', '?')}"
            )

    def _render_evaluation(self) -> None:
        result = st.session_state.evaluation
        st.subheader("Évaluation")
        st.metric("Score final", f"{result.final_score}/100")

        score_frame = pd.DataFrame(
            {"Critère": list(result.scores.keys()), "Score": list(result.scores.values())}
        )
        st.bar_chart(score_frame.set_index("Critère"))

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("**Points forts**")
            for item in result.strengths:
                st.write(f"- {item}")
        with col_b:
            st.markdown("**Axes d'amélioration**")
            for item in result.weaknesses:
                st.write(f"- {item}")
        with col_c:
            st.markdown("**Conseils**")
            for item in result.suggestions:
                st.write(f"- {item}")

        if st.button("Démarrer un autre appel", type="primary"):
            self._reset()
            st.rerun()

    def _render_agent_voice_input(self) -> None:
        st.markdown("**Parlez au prospect**")
        supports_audio_input = hasattr(st, "audio_input")
        transcript_key = "pending_agent_transcript"

        if supports_audio_input:
            recording = st.audio_input("Enregistrez votre réponse", key="agent_recording")
            if recording is not None:
                self._auto_process_recording(recording, transcript_key)
        else:
            st.warning("Votre version de Streamlit ne supporte pas `st.audio_input`. Utilisez le champ texte.")

        trainee_reply = st.text_area(
            "Transcription / réponse de l'agent",
            value=st.session_state.get(transcript_key, ""),
            height=120,
            placeholder="Parlez dans le micro — la transcription se fait automatiquement.",
        )
        col_a, col_b = st.columns([0.7, 0.3])
        with col_a:
            if st.button("Envoyer au prospect", type="primary", use_container_width=True):
                self._send_reply(trainee_reply)
                st.session_state[transcript_key] = ""
        with col_b:
            if st.button("Effacer", use_container_width=True):
                st.session_state[transcript_key] = ""
                st.rerun()

    def _auto_process_recording(self, recording: object, transcript_key: str) -> None:
        """Transcribe new recordings automatically and send them to the prospect."""
        audio_bytes = recording.getvalue()
        if not audio_bytes:
            return

        audio_hash = hashlib.md5(audio_bytes).hexdigest()
        processed = st.session_state.setdefault("processed_audio_hashes", set())
        if audio_hash in processed:
            return

        try:
            with st.spinner("Transcription AssemblyAI…"):
                transcript = self._transcribe_upload(recording)
            processed.add(audio_hash)
            st.session_state[transcript_key] = transcript

            if transcript.strip() and not st.session_state.engine.ended:
                with st.spinner("Le prospect répond…"):
                    self._send_reply(transcript, rerun=False)
                st.session_state[transcript_key] = ""
                st.rerun()
        except AudioTranscriptionError as exc:
            st.error(str(exc))

    def _render_reference_recordings(self) -> None:
        with st.sidebar.expander("Importer vos appels (entraînement)", expanded=False):
            raw_dir = PROJECT_ROOT / "data" / "raw_calls"
            raw_dir.mkdir(parents=True, exist_ok=True)
            dialogue_count = len(list(TRANSCRIPTS_DIR.glob("*_dialogue.json")))
            pair_count = len(self._get_dialogue_library().pairs)
            st.write(
                f"**{dialogue_count}** appels transcrits · **{pair_count}** paires agent→prospect"
            )
            st.markdown(
                "1. Déposez vos WAV/MP3 ci-dessous **ou** dans `data/raw_calls/`\n"
                "2. Lancez dans le terminal :\n"
                "```bash\nbash scripts/import_all_calls.sh\n```\n"
                "3. Choisissez le modèle **prospect-energie** dans la barre latérale"
            )
            bulk = st.file_uploader(
                "Vos appels (batch)",
                type=["wav", "mp3", "m4a", "ogg"],
                accept_multiple_files=True,
                key="bulk_calls_upload",
            )
            if bulk and st.button("Enregistrer dans raw_calls/", use_container_width=True):
                saved = 0
                for upload in bulk:
                    dest = raw_dir / upload.name
                    dest.write_bytes(upload.getvalue())
                    saved += 1
                st.success(f"{saved} fichier(s) enregistré(s). Lancez `bash scripts/import_all_calls.sh`")

        with st.sidebar.expander("Appels réels (style du prospect)"):
            st.write(
                "Ajoutez un enregistrement d'un vrai appel. Il sera transcrit et utilisé "
                "pour imiter le ton et les réponses du prospect."
            )
            line_count = len(self._get_dialogue_library().pairs)
            st.caption(f"{line_count} échanges agent→prospect chargés (AssemblyAI).")

            uploads = st.file_uploader(
                "Enregistrement d'appel réel",
                type=["wav", "mp3", "m4a", "ogg", "webm"],
                accept_multiple_files=True,
            )
            if uploads and st.button("Transcrire et utiliser", use_container_width=True):
                saved = 0
                for upload in uploads:
                    try:
                        self._ingest_reference_recording(upload)
                        saved += 1
                    except AudioTranscriptionError as exc:
                        st.warning(f"{upload.name}: {exc}")
                if saved:
                    st.success(f"{saved} enregistrement(s) ajouté(s). Relancez l'appel pour prendre en compte.")

            for index, transcript in enumerate(st.session_state.get("style_examples", []), start=1):
                st.caption(f"Transcription brute {index}")
                st.write(transcript[:400])

    def _start_conversation(self, profile: str, difficulty: str) -> None:
        engine = ConversationEngine.from_paths(
            profile=profile,
            difficulty=difficulty,
            knowledge_base_path=KNOWLEDGE_PATH,
            call_models_path=CALL_MODELS_PATH,
            transcripts_dir=TRANSCRIPTS_DIR,
            model=st.session_state.get("ollama_model", "qwen2.5:7b"),
            use_llm=st.session_state.get("use_llm", False),
        )
        st.session_state.engine = engine
        st.session_state.evaluation = None
        st.session_state.last_spoken_customer_index = -1
        st.session_state.processed_audio_hashes = set()
        st.session_state.pending_agent_transcript = ""
        try:
            engine.start()
        except LLMError as exc:
            del st.session_state.engine
            st.error(str(exc))

    def _send_reply(self, trainee_reply: str, *, rerun: bool = True) -> None:
        if not trainee_reply.strip():
            st.warning("Enregistrez ou écrivez une réponse avant d'envoyer.")
            return
        try:
            st.session_state.engine.respond_to_trainee(trainee_reply)
        except (LLMError, ValueError) as exc:
            st.error(str(exc))
            return
        if rerun:
            st.rerun()

    def _evaluate(self) -> None:
        engine = st.session_state.get("engine")
        if not engine:
            return
        evaluator = Evaluator(KnowledgeBase(KNOWLEDGE_PATH))
        st.session_state.evaluation = evaluator.evaluate(
            history=engine.history,
            profile=engine.profile,
            difficulty=engine.difficulty,
        )

    def _reset(self) -> None:
        for key in ("engine", "evaluation", "processed_audio_hashes", "pending_agent_transcript"):
            if key in st.session_state:
                del st.session_state[key]

    def _ensure_session_defaults(self) -> None:
        st.session_state.setdefault("evaluation", None)
        st.session_state.setdefault("style_examples", self._load_default_style_examples())
        st.session_state.setdefault("pending_agent_transcript", "")
        st.session_state.setdefault("last_spoken_customer_index", -1)
        st.session_state.setdefault("processed_audio_hashes", set())

    def _transcribe_upload(self, upload: object) -> str:
        audio_bytes = upload.getvalue()
        suffix = Path(getattr(upload, "name", "recording.wav")).suffix or ".wav"
        try:
            return transcribe_agent_bytes(audio_bytes, suffix=suffix)
        except ProTranscriptionError as exc:
            if "Clé AssemblyAI manquante" in str(exc):
                return self._get_whisper_transcriber().transcribe_bytes(audio_bytes, suffix=suffix)
            raise AudioTranscriptionError(str(exc)) from exc

    def _ingest_reference_recording(self, upload: object) -> None:
        """Save a reference recording and its transcript for prospect-style training."""
        REFERENCE_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

        upload_name = Path(getattr(upload, "name", "reference.wav"))
        stem = upload_name.stem
        suffix = upload_name.suffix or ".wav"
        audio_path = REFERENCE_RECORDINGS_DIR / f"{stem}{suffix}"
        audio_path.write_bytes(upload.getvalue())

        transcript = self._transcribe_upload(upload)
        style_examples = list(st.session_state.get("style_examples", []))
        style_examples.append(transcript)
        st.session_state.style_examples = style_examples[-5:]

        json_path = TRANSCRIPTS_DIR / f"{stem}.json"
        txt_path = TRANSCRIPTS_DIR / f"{stem}.txt"
        payload = {
            "audio_file": str(audio_path),
            "source_upload": upload_name.name,
            "text": transcript,
            "segments": [{"start": 0.0, "end": 0.0, "text": part} for part in transcript.split(". ") if part.strip()],
        }
        with json_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        txt_path.write_text(transcript + "\n", encoding="utf-8")

    def _speak_latest_customer_once(self) -> None:
        if not st.session_state.get("voice_enabled", True):
            return
        history = st.session_state.engine.history
        for index in range(len(history) - 1, -1, -1):
            if history[index]["role"] == "customer":
                if index > st.session_state.get("last_spoken_customer_index", -1):
                    self._speak_text(history[index]["content"], force_key=f"auto_{index}")
                    st.session_state.last_spoken_customer_index = index
                return

    @staticmethod
    def _speak_text(text: str, force_key: str) -> None:
        text_json = json.dumps(text)
        key_json = json.dumps(force_key)
        components.html(
            f"""
            <script>
            const text = {text_json};
            const key = {key_json};

            function pickFrenchVoice() {{
                const voices = window.parent.speechSynthesis.getVoices();
                const frenchVoices = voices.filter((voice) =>
                    voice.lang && voice.lang.toLowerCase().startsWith("fr")
                );
                if (frenchVoices.length === 0) {{
                    return null;
                }}

                const preferredNames = [
                    "Amélie", "Thomas", "Marie", "Audrey", "Céline", "Jacques",
                    "Google français", "Microsoft Hortense", "Microsoft Julie",
                    "Microsoft Paul", "Daniel", "Virginie"
                ];
                for (const name of preferredNames) {{
                    const match = frenchVoices.find((voice) =>
                        voice.name.includes(name)
                    );
                    if (match) {{
                        return match;
                    }}
                }}

                const localFrench = frenchVoices.find((voice) => voice.localService);
                return localFrench || frenchVoices[0];
            }}

            window.parent.__spokenKeys = window.parent.__spokenKeys || new Set();
            if (!window.parent.__spokenKeys.has(key)) {{
                window.parent.__spokenKeys.add(key);
                const speak = () => {{
                    const utterance = new SpeechSynthesisUtterance(text);
                    const frenchVoice = pickFrenchVoice();
                    utterance.lang = frenchVoice ? frenchVoice.lang : "fr-FR";
                    if (frenchVoice) {{
                        utterance.voice = frenchVoice;
                    }}
                    utterance.rate = 1.05;
                    utterance.pitch = 1.0;
                    window.parent.speechSynthesis.cancel();
                    window.parent.speechSynthesis.speak(utterance);
                }};
                if (window.parent.speechSynthesis.getVoices().length === 0) {{
                    window.parent.speechSynthesis.onvoiceschanged = speak;
                }} else {{
                    speak();
                }}
            }}
            </script>
            """,
            height=0,
        )

    @staticmethod
    @st.cache_resource(show_spinner=False)
    def _get_whisper_transcriber():
        return live_call_transcriber()

    @staticmethod
    @st.cache_resource(show_spinner=False)
    def _get_dialogue_library() -> DialogueLibrary:
        return DialogueLibrary(TRANSCRIPTS_DIR)

    def _profile_label(self, profile_id: str) -> str:
        for profile in self.profiles:
            if profile["id"] == profile_id:
                return str(profile["name"])
        return profile_id

    def _difficulty_label(self, difficulty_id: str) -> str:
        for label, value in self.difficulties.items():
            if value == difficulty_id:
                return label
        return difficulty_id

    @staticmethod
    def _load_profiles() -> list[dict[str, object]]:
        with PROFILES_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)["profiles"]

    @staticmethod
    def _load_default_style_examples() -> list[str]:
        if not STYLE_EXAMPLES_PATH.exists():
            return []
        with STYLE_EXAMPLES_PATH.open("r", encoding="utf-8") as file:
            raw = json.load(file)

        examples = raw.get("examples", [])
        loaded: list[str] = []
        for example in examples:
            if isinstance(example, dict):
                text = str(example.get("text", "")).strip()
            else:
                text = str(example).strip()
            if text:
                loaded.append(text)
        return loaded


def main() -> None:
    """Run the Streamlit app."""
    StreamlitCallSimulator().render()


if __name__ == "__main__":
    main()
