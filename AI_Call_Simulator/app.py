"""Application entrypoint — navigation Lead & Connect."""

from __future__ import annotations

import streamlit as st

from ui.brand_theme import inject_global_css, inject_sidebar_css

st.set_page_config(
    page_title="Lead & Connect Training",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_css()
inject_sidebar_css()

pg = st.navigation(
    {
        "Entraînement": [
            st.Page(
                "pages/1_Identification_Agent.py",
                title="Identification agent",
                icon="👤",
            ),
            st.Page(
                "pages/_mode1_agent.py",
                title="Mode 1 : vous êtes l'agent",
                icon="📞",
                default=True,
            ),
            st.Page(
                "pages/2_Mode_Prospect_IA.py",
                title="Mode 2 : vous êtes le prospect",
                icon="🎭",
            ),
        ],
        "Administration": [
            st.Page(
                "pages/_Historique_Appels.py",
                title="Historique appels",
                icon="📋",
            ),
            st.Page(
                "pages/_Export_Examen_Certif.py",
                title="Export examen certif",
                icon="📊",
            ),
            st.Page(
                "pages/_Reevaluer_Agents.py",
                title="Réévaluer agents",
                icon="🔄",
            ),
        ],
    },
    position="sidebar",
    expanded=True,
)

pg.run()
