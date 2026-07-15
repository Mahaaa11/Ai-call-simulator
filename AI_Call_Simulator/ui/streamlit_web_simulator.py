"""Streamlit host — Version 1 : vous êtes l'agent commercial."""

from __future__ import annotations

from pathlib import Path

from ui.simulator_host import run_simulator

SIMULATION_HTML = Path(__file__).resolve().parents[1] / "web" / "simulation.html"


def main() -> None:
    run_simulator(
        SIMULATION_HTML,
        page_title="Simulateur d'appels IA — Mode Agent",
        page_icon="📞",
        iframe_height=1180,
    )


if __name__ == "__main__":
    main()
