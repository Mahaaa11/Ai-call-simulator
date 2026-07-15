"""Streamlit host — Version 1 : vous êtes l'agent commercial."""

from __future__ import annotations

from pathlib import Path

from ui.simulator_host import run_simulator

SIMULATION_HTML = Path(__file__).resolve().parents[1] / "web" / "simulation.html"


def main() -> None:
    from ui.simulator_host import COMPONENT_FRONTEND
    from ui.simulation_component import simulation_app_v1

    run_simulator(
        SIMULATION_HTML,
        page_title="Simulateur d'appels IA — Mode Agent",
        page_icon="📞",
        iframe_height=1180,
        component=simulation_app_v1,
        frontend_dir=COMPONENT_FRONTEND / "v1",
        extra_config={"v1TrainingEvolution": True},
    )


if __name__ == "__main__":
    main()
