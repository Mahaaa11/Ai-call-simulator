from __future__ import annotations

import base64
import uuid
from pathlib import Path

from .backends.factory import get_avatar_backend, get_idle_backend
from .tts import synthesize

ASSETS = Path(__file__).resolve().parent.parent / "assets"
PORTRAITS = {
    "female": ASSETS / "prospect-female-calm.png",
    "male": ASSETS / "prospect-male-calm.png",
}


def resolve_portrait(gender: str | None) -> Path:
    key = "female" if gender in {"female", "f", "woman"} else "male"
    return PORTRAITS.get(key, PORTRAITS["female"])


async def run_speak_pipeline(
    *,
    text: str,
    voice: str | None,
    tone: str,
    gender: str | None,
    session_id: str | None = None,
):
    """TTS → MuseTalk (+ optional LivePortrait idle). Yields wire-format dicts."""
    sid = session_id or uuid.uuid4().hex
    portrait = resolve_portrait(gender)

    yield {"type": "session_start", "session_id": sid}

    audio = await synthesize(text[:500], voice, tone or "calm")
    yield {
        "type": "audio",
        "data": base64.b64encode(audio).decode("ascii"),
        "mime": "audio/mpeg",
    }

    avatar = get_avatar_backend()
    async for event in avatar.generate(audio, portrait, session_id=sid):
        if event["type"] == "video_chunk":
            yield {
                "type": "video_chunk",
                "data": base64.b64encode(event["data"]).decode("ascii"),
                "mime": event.get("mime", "video/mp4"),
            }
        else:
            yield event

    yield {"type": "done", "session_id": sid}


async def run_idle_pipeline(*, gender: str | None, session_id: str | None = None):
    sid = session_id or uuid.uuid4().hex
    portrait = resolve_portrait(gender)
    idle = get_idle_backend()

    yield {"type": "idle_start", "session_id": sid}
    async for frame in idle.stream_idle(portrait, session_id=sid):
        if frame["type"] == "idle_frame":
            yield {
                "type": "idle_frame",
                "data": base64.b64encode(frame["data"]).decode("ascii"),
                "mime": frame.get("mime", "image/jpeg"),
            }
