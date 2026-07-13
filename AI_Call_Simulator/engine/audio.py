"""Speech-to-text helpers for live practice calls and reference recordings."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


FRENCH_CALL_INITIAL_PROMPT = (
    "Bonjour madame, bonjour monsieur. Appel commercial en français pour la facture d'électricité. "
    "Société Ogini, comparateur d'énergie. Fournisseurs : Alpiq, EDF, Engie, TotalEnergies, HomeEnergy. "
    "Kilowatt-heure, kWh, heures creuses, heures pleines, abonnement compteur, consommation, "
    "régularisation, prélèvement, RIB, IBAN, code SMS, sans engagement, contrat deux ans."
)


class AudioTranscriptionError(RuntimeError):
    """Raised when audio transcription cannot be completed."""


@dataclass
class WhisperTranscriber:
    """Transcribes French call audio with Faster-Whisper."""

    model_size: str = "small"
    language: str = "fr"
    compute_type: str = "int8"
    beam_size: int = 5
    initial_prompt: str = FRENCH_CALL_INITIAL_PROMPT
    _model: Any | None = field(default=None, init=False, repr=False)

    def transcribe_bytes(self, audio_bytes: bytes, suffix: str = ".wav") -> str:
        """Transcribe an in-memory audio recording."""
        return self.transcribe_detailed_bytes(audio_bytes, suffix=suffix)["text"]

    def transcribe_detailed_bytes(self, audio_bytes: bytes, suffix: str = ".wav") -> dict[str, Any]:
        """Transcribe in-memory audio and return text plus segments."""
        if not audio_bytes:
            raise AudioTranscriptionError("Le fichier audio est vide.")

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as temp_file:
            temp_file.write(audio_bytes)
            temp_file.flush()
            return self.transcribe_detailed_file(Path(temp_file.name))

    def transcribe_file(self, audio_path: Path) -> str:
        """Transcribe an audio file from disk."""
        return self.transcribe_detailed_file(audio_path)["text"]

    def transcribe_detailed_file(self, audio_path: Path) -> dict[str, Any]:
        """Transcribe an audio file and return structured output."""
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise AudioTranscriptionError(
                "Faster-Whisper n'est pas installé. Lancez: pip install -r requirements.txt"
            ) from exc

        try:
            if self._model is None:
                self._model = WhisperModel(self.model_size, compute_type=self.compute_type)
            segments_iter, info = self._model.transcribe(
                str(audio_path),
                language=self.language,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 200},
                beam_size=self.beam_size,
                best_of=2,
                temperature=0.0,
                initial_prompt=self.initial_prompt,
                condition_on_previous_text=True,
                word_timestamps=False,
            )
            segment_rows = [
                {
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": segment.text.strip(),
                }
                for segment in segments_iter
                if segment.text.strip()
            ]
        except Exception as exc:
            raise AudioTranscriptionError(f"Transcription impossible: {exc}") from exc

        text = " ".join(row["text"] for row in segment_rows).strip()
        if not text:
            raise AudioTranscriptionError("Aucune parole détectée dans l'audio.")

        return {
            "text": text,
            "segments": segment_rows,
            "language": info.language or self.language,
            "language_probability": round(float(info.language_probability or 0), 4),
            "duration": round(float(info.duration or 0), 2),
            "model": self.model_size,
        }


def live_call_transcriber() -> WhisperTranscriber:
    """Fast settings for short agent microphone clips during practice."""
    return WhisperTranscriber(model_size="small", beam_size=3)


def reference_call_transcriber() -> WhisperTranscriber:
    """High-quality settings for full call recordings."""
    return WhisperTranscriber(model_size="medium", beam_size=5, compute_type="int8")
