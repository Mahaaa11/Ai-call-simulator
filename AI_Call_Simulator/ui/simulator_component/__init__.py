"""Unified Streamlit component: simulation iframe + MySQL save bridge."""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).resolve().parent / "frontend"
simulator_frame = components.declare_component(
    "simulator_frame",
    path=str(_COMPONENT_DIR),
)
