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
    [
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
    position="sidebar",
    expanded=True,
)

pg.run()
