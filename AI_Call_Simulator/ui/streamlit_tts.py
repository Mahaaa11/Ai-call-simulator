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

TONE_PROSODY = {
    "calm": 'rate="-5%" pitch="+0%"',
    "tense": 'rate="+8%" pitch="+2%"',
    "angry": 'rate="+15%" pitch="+8%" volume="loud"',
    "shouting": 'rate="+28%" pitch="+12%" volume="x-loud"',
}


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_ssml(text: str, tone: str = "calm") -> str:
    prosody = TONE_PROSODY.get(tone, TONE_PROSODY["calm"])
    clean = _escape_xml(text)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="fr-FR">'
        f"<prosody {prosody}>{clean}</prosody></speak>"
    )

_loop = asyncio.new_event_loop()
_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_thread.start()


async def _synthesize(text: str, voice: str, tone: str = "calm") -> bytes:
    if edge_tts is None:
        raise RuntimeError("edge-tts non installé")
    payload = build_ssml(text, tone) if tone and tone != "calm" else text
    communicate = edge_tts.Communicate(payload, voice)
    parts: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            parts.append(chunk["data"])
    audio = b"".join(parts)
    if not audio:
        raise RuntimeError("edge-tts n'a renvoyé aucun audio")
    return audio


def synthesize_speech(text: str, *, gender: str = "female", tone: str = "calm") -> bytes:
    clean = (text or "").strip()
    if not clean:
        raise ValueError("Texte TTS vide")
    if len(clean) > 500:
        clean = clean[:500]
    voice = VOICE_BY_GENDER.get(gender, VOICE_BY_GENDER["female"])
    future = asyncio.run_coroutine_threadsafe(_synthesize(clean, voice, tone), _loop)
    return future.result(timeout=45)
