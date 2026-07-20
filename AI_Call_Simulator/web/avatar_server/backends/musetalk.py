"""
MuseTalk adapter — lip-sync from portrait + audio.

Set MUSETALK_URL to a running MuseTalk HTTP service, e.g.:
  POST /infer  multipart: image, audio  →  video/mp4 stream or JSON {video_b64}

Official repo: https://github.com/TMElyralab/MuseTalk
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import AsyncIterator

import httpx

from .base import AvatarBackend

DEFAULT_URL = os.getenv("MUSETALK_URL", "http://127.0.0.1:8780")


class MuseTalkBackend(AvatarBackend):
    name = "musetalk"

    def __init__(self, base_url: str | None = None, timeout: float = 120.0) -> None:
        self.base_url = (base_url or DEFAULT_URL).rstrip("/")
        self.timeout = timeout

    async def generate(
        self,
        audio: bytes,
        portrait: Path,
        *,
        session_id: str,
    ) -> AsyncIterator[dict]:
        if not portrait.exists():
            yield {"type": "fallback_loop"}
            return

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with portrait.open("rb") as img_f:
                    files = {
                        "image": (portrait.name, img_f, "image/png"),
                        "audio": ("speech.mp3", audio, "audio/mpeg"),
                    }
                    data = {"session_id": session_id}
                    resp = await client.post(f"{self.base_url}/infer", files=files, data=data)
                    resp.raise_for_status()
                    ctype = resp.headers.get("content-type", "")

                    if "video" in ctype:
                        yield {"type": "video_chunk", "data": resp.content, "mime": ctype.split(";")[0]}
                        return

                    payload = resp.json()
                    video_b64 = payload.get("video_b64") or payload.get("video")
                    if video_b64:
                        yield {
                            "type": "video_chunk",
                            "data": base64.b64decode(video_b64),
                            "mime": payload.get("mime", "video/mp4"),
                        }
                        return
        except Exception as exc:
            print(f"[MuseTalk] {exc} — falling back to loop video")
            yield {"type": "fallback_loop", "error": str(exc)}
            return

        yield {"type": "fallback_loop"}
