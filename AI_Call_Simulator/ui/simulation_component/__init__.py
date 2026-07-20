"""Streamlit component: simulation page with direct MySQL save."""

from __future__ import annotations

import shutil
from pathlib import Path

import streamlit.components.v1 as components

_FRONTEND = Path(__file__).resolve().parent / "frontend"
_FRONTEND_V1 = _FRONTEND / "v1"
_FRONTEND_V2 = _FRONTEND / "v2"
_LIB = _FRONTEND / "streamlit-component-lib.js"


def _ensure_frontend_dir(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    lib_dst = target / "streamlit-component-lib.js"
    if _LIB.exists() and not lib_dst.exists():
        shutil.copy2(_LIB, lib_dst)
    if not (target / "index.html").exists():
        (target / "index.html").write_text(
            "<!DOCTYPE html><html><body>Chargement…</body></html>",
            encoding="utf-8",
        )


_ensure_frontend_dir(_FRONTEND_V1)
_ensure_frontend_dir(_FRONTEND_V2)

# Sync component HTML from source at import (Streamlit Cloud may not rewrite at runtime).
try:
    from ui.simulator_host import _sync_component_index

    _root = Path(__file__).resolve().parents[2]
    _v1_html = _root / "web" / "simulation.html"
    _prospect_html = _root / "web" / "simulation_prospect.html"
    if _v1_html.exists():
        _sync_component_index(_v1_html, _FRONTEND_V1)
    if _prospect_html.exists():
        _sync_component_index(_prospect_html, _FRONTEND_V2)
except Exception:
    pass

simulation_app_v1 = components.declare_component(
    "simulation_app_v1",
    path=str(_FRONTEND_V1),
)
simulation_app_v2 = components.declare_component(
    "simulation_app_v2",
    path=str(_FRONTEND_V2),
)
