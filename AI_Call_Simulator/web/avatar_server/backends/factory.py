from __future__ import annotations

import os

from .base import AvatarBackend, IdleBackend
from .liveportrait import LivePortraitIdleBackend
from .musetalk import MuseTalkBackend
from .stub import StubAvatarBackend, StubIdleBackend


def get_avatar_backend() -> AvatarBackend:
    mode = os.getenv("AVATAR_BACKEND", "stub").lower()
    if mode in {"musetalk", "musetalk+liveportrait"}:
        return MuseTalkBackend()
    return StubAvatarBackend()


def get_idle_backend() -> IdleBackend:
    mode = os.getenv("AVATAR_BACKEND", "stub").lower()
    if mode in {"liveportrait", "musetalk+liveportrait", "hallo2"}:
        return LivePortraitIdleBackend()
    return StubIdleBackend()
