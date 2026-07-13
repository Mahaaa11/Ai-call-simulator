"""Streamlit component: simulation page with direct MySQL save."""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_FRONTEND = Path(__file__).resolve().parent / "frontend"
simulation_app = components.declare_component(
    "simulation_app",
    path=str(_FRONTEND),
)
