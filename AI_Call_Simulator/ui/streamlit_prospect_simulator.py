"""Streamlit host — Version 2 : vous êtes le prospect, l'IA est l'agent."""

from __future__ import annotations

from pathlib import Path

from ui.simulator_host import run_simulator

SIMULATION_HTML = Path(__file__).resolve().parents[1] / "web" / "simulation_prospect.html"


def main() -> None:
    run_simulator(
        SIMULATION_HTML,
        page_title="Simulateur — Mode Prospect",
        page_icon="🎭",
        iframe_height=1050,
    )


if __name__ == "__main__":
    main()
