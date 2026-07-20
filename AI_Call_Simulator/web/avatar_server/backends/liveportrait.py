"""
LivePortrait / Hallo2 idle animation adapter.

Set LIVEPORTRAIT_URL to a service exposing:
  POST /idle/stream  multipart: image  →  chunked JPEG frames

LivePortrait: https://github.com/KwaiVGI/LivePortrait
Hallo2:       https://github.com/fudan-generative-vision/hallo2
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator

import httpx

from .base import IdleBackend

DEFAULT_URL = os.getenv("LIVEPORTRAIT_URL", "http://127.0.0.1:8781")


class LivePortraitIdleBackend(IdleBackend):
    name = "liveportrait"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or DEFAULT_URL).rstrip("/")

    async def stream_idle(
        self,
        portrait: Path,
        *,
        session_id: str,
    ) -> AsyncIterator[dict]:
        if not portrait.exists():
            return

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with portrait.open("rb") as img_f:
                    files = {"image": (portrait.name, img_f, "image/png")}
                    data = {"session_id": session_id, "mode": "idle"}
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/idle/stream",
                        files=files,
                        data=data,
                    ) as resp:
                        resp.raise_for_status()
                        async for chunk in resp.aiter_bytes():
                            if chunk:
                                yield {"type": "idle_frame", "data": chunk, "mime": "image/jpeg"}
        except Exception as exc:
            print(f"[LivePortrait idle] {exc}")
