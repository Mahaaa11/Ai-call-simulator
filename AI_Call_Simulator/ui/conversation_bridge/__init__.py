"""Minimal bridge: receives conversation saves from simulation iframe."""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_BRIDGE_DIR = Path(__file__).resolve().parent / "frontend"
conversation_bridge = components.declare_component(
    "conversation_bridge",
    path=str(_BRIDGE_DIR),
)
