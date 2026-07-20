"""French TTS via edge-tts (shared with legacy tts_server.py)."""

from __future__ import annotations

import asyncio
import threading

try:
    import edge_tts
except ImportError as exc:
    raise ImportError("Install edge-tts: pip install edge-tts") from exc

VOICE = "fr-FR-DeniseNeural"
VOICES = {
    "fr-FR-DeniseNeural": "fr-FR-DeniseNeural",
    "fr-FR-HenriNeural": "fr-FR-HenriNeural",
    "female": "fr-FR-DeniseNeural",
    "male": "fr-FR-HenriNeural",
}
TONE_PROSODY = {
    "calm": 'rate="-5%" pitch="+0%"',
    "tense": 'rate="+8%" pitch="+2%"',
    "angry": 'rate="+15%" pitch="+8%" volume="loud"',
    "shouting": 'rate="+28%" pitch="+12%" volume="x-loud"',
}

_loop = asyncio.new_event_loop()
_thread = threading.Thread(target=_loop.run_forever, daemon=True, name="edge-tts-loop")
_thread.start()


async def synthesize(text: str, voice: str | None = None, tone: str = "calm") -> bytes:
    voice_name = VOICES.get(voice or "", voice) or VOICE
    if voice_name not in VOICES.values():
        voice_name = VOICE

    payload = text
    if tone and tone != "calm":
        prosody = TONE_PROSODY.get(tone, TONE_PROSODY["calm"])
        clean = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        payload = (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="fr-FR">'
            f"<prosody {prosody}>{clean}</prosody></speak>"
        )

    communicate = edge_tts.Communicate(payload, voice_name)
    parts: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            parts.append(chunk["data"])
    audio = b"".join(parts)
    if not audio:
        raise RuntimeError("edge-tts returned empty audio")
    return audio


def synthesize_sync(text: str, voice: str | None = None, tone: str = "calm") -> bytes:
    future = asyncio.run_coroutine_threadsafe(synthesize(text, voice, tone), _loop)
    return future.result(timeout=45)
