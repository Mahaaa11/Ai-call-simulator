from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncIterator


class AvatarBackend(ABC):
    """Audio-driven talking-head generation (MuseTalk, Wav2Lip, etc.)."""

    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        audio: bytes,
        portrait: Path,
        *,
        session_id: str,
    ) -> AsyncIterator[dict]:
        """
        Yield streaming events:
          {"type": "video_chunk", "data": bytes, "mime": "video/mp4"}
          {"type": "fallback_loop"}  — client uses pre-rendered idle/speaking loops
        """


class IdleBackend(ABC):
    """Subtle idle motion (LivePortrait, Hallo2)."""

    name: str = "base"

    @abstractmethod
    async def stream_idle(
        self,
        portrait: Path,
        *,
        session_id: str,
    ) -> AsyncIterator[dict]:
        """
        Yield:
          {"type": "idle_frame", "data": bytes, "mime": "image/jpeg"}
        """
