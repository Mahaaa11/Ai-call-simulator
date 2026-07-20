"""Fallback backend: audio only, client keeps loop videos."""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from .base import AvatarBackend, IdleBackend


class StubAvatarBackend(AvatarBackend):
    name = "stub"

    async def generate(
        self,
        audio: bytes,
        portrait: Path,
        *,
        session_id: str,
    ) -> AsyncIterator[dict]:
        yield {"type": "fallback_loop"}


class StubIdleBackend(IdleBackend):
    name = "stub"

    async def stream_idle(
        self,
        portrait: Path,
        *,
        session_id: str,
    ) -> AsyncIterator[dict]:
        if False:
            yield {}
