"""Hosted TTS for Streamlit (edge-tts, French voices)."""

from __future__ import annotations

import asyncio
import threading

try:
    import edge_tts
except ImportError:
    edge_tts = None  # type: ignore

VOICE_BY_GENDER = {
    "female": "fr-FR-DeniseNeural",
    "male": "fr-FR-HenriNeural",
}

_loop = asyncio.new_event_loop()
_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_thread.start()


async def _synthesize(text: str, voice: str) -> bytes:
    if edge_tts is None:
        raise RuntimeError("edge-tts non installé")
    communicate = edge_tts.Communicate(text, voice)
    parts: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            parts.append(chunk["data"])
    audio = b"".join(parts)
    if not audio:
        raise RuntimeError("edge-tts n'a renvoyé aucun audio")
    return audio


def synthesize_speech(text: str, *, gender: str = "female") -> bytes:
    clean = (text or "").strip()
    if not clean:
        raise ValueError("Texte TTS vide")
    if len(clean) > 500:
        clean = clean[:500]
    voice = VOICE_BY_GENDER.get(gender, VOICE_BY_GENDER["female"])
    future = asyncio.run_coroutine_threadsafe(_synthesize(clean, voice), _loop)
    return future.result(timeout=45)
