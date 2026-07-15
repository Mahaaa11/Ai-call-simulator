"""Streamlit component: simulation page with direct MySQL save."""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_FRONTEND = Path(__file__).resolve().parent / "frontend"
_FRONTEND_V1 = _FRONTEND / "v1"
_FRONTEND_V2 = _FRONTEND / "v2"

simulation_app = components.declare_component(
    "simulation_app",
    path=str(_FRONTEND),
)
simulation_app_v1 = components.declare_component(
    "simulation_app_v1",
    path=str(_FRONTEND_V1),
)
simulation_app_v2 = components.declare_component(
    "simulation_app_v2",
    path=str(_FRONTEND_V2),
)
