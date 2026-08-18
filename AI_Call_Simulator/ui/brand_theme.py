"""Lead & Connect — Streamlit brand styling."""

from __future__ import annotations

import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Outfit', system-ui, sans-serif !important;
        }

        .stApp {
            background:
                radial-gradient(ellipse 80% 50% at 0% 0%, rgba(0, 130, 127, 0.08), transparent 55%),
                radial-gradient(ellipse 60% 40% at 100% 0%, rgba(217, 128, 46, 0.10), transparent 50%),
                linear-gradient(180deg, #f7f9fc 0%, #ffffff 45%, #f4f8fb 100%);
        }

        header[data-testid="stHeader"] {
            background: rgba(255, 255, 255, 0.72);
            backdrop-filter: blur(12px);
        }

        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1100px;
        }

        .lc-hero {
            text-align: center;
            padding: 2rem 1.5rem 2.2rem;
            margin: 0 0 1.5rem;
            border-radius: 22px;
            background: linear-gradient(135deg, #002D58 0%, #003d75 42%, #00827F 100%);
            color: #fff;
            box-shadow:
                0 18px 40px rgba(0, 45, 88, 0.22),
                0 0 0 1px rgba(255, 255, 255, 0.08) inset;
            position: relative;
            overflow: hidden;
        }

        .lc-hero::before {
            content: "";
            position: absolute;
            inset: -40% 20% auto -20%;
            height: 140%;
            background: radial-gradient(circle, rgba(217, 128, 46, 0.28), transparent 62%);
            pointer-events: none;
        }

        .lc-hero::after {
            content: "";
            position: absolute;
            right: -8%;
            bottom: -50%;
            width: 220px;
            height: 220px;
            background: radial-gradient(circle, rgba(255, 255, 255, 0.12), transparent 70%);
            pointer-events: none;
        }

        .lc-hero-inner { position: relative; z-index: 1; }

        .lc-badge {
            display: inline-block;
            padding: 0.35rem 0.9rem;
            border-radius: 999px;
            background: rgba(217, 128, 46, 0.22);
            border: 1px solid rgba(217, 128, 46, 0.45);
            color: #ffd4a8;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 0.75rem;
        }

        .lc-hero h1 {
            margin: 0;
            font-size: clamp(1.55rem, 3.5vw, 2.15rem);
            font-weight: 800;
            line-height: 1.15;
            color: #fff;
        }

        .lc-hero p {
            margin: 0.65rem auto 0;
            max-width: 640px;
            color: rgba(255, 255, 255, 0.88);
            font-size: 1rem;
            line-height: 1.5;
        }

        .lc-card {
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid rgba(0, 45, 88, 0.08);
            border-radius: 18px;
            padding: 1.25rem 1.35rem;
            margin-bottom: 1rem;
            box-shadow: 0 8px 28px rgba(0, 45, 88, 0.07);
            backdrop-filter: blur(8px);
        }

        .lc-card h3 {
            margin: 0 0 0.35rem;
            font-size: 1.05rem;
            color: #002D58;
        }

        .lc-card p {
            margin: 0;
            color: #5c6570;
            font-size: 0.92rem;
            line-height: 1.45;
        }

        .lc-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 0.85rem;
            margin: 1rem 0 1.25rem;
        }

        .lc-stat {
            background: linear-gradient(145deg, #ffffff, #f3f7fb);
            border: 1px solid rgba(0, 45, 88, 0.08);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            text-align: center;
            box-shadow: 0 6px 18px rgba(0, 45, 88, 0.06);
        }

        .lc-stat .num {
            font-size: 1.75rem;
            font-weight: 800;
            color: #00827F;
            line-height: 1.1;
        }

        .lc-stat .lbl {
            margin-top: 0.25rem;
            font-size: 0.82rem;
            color: #667085;
            font-weight: 600;
        }

        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, #ffffff, #f0f7f6);
            border: 1px solid rgba(0, 130, 127, 0.15);
            border-radius: 16px;
            padding: 0.75rem 1rem;
            box-shadow: 0 8px 20px rgba(0, 130, 127, 0.08);
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #00827F, #006b68) !important;
            border: none !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            box-shadow: 0 8px 22px rgba(0, 130, 127, 0.28) !important;
        }

        .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 12px 26px rgba(0, 130, 127, 0.34) !important;
        }

        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            border-radius: 12px !important;
        }

        iframe { border: none !important; border-radius: 18px; }

        #MainMenu, footer { visibility: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(title: str, subtitle: str, badge: str = "Lead & Connect") -> None:
    st.markdown(
        f"""
        <div class="lc-hero">
          <div class="lc-hero-inner">
            <span class="lc-badge">{badge}</span>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_feature_cards() -> None:
    st.markdown(
        """
        <div class="lc-grid">
          <div class="lc-card">
            <h3>🎯 Entraînement réaliste</h3>
            <p>Scénarios Engie, objections RGPD et profils clients variés.</p>
          </div>
          <div class="lc-card">
            <h3>📊 Évaluation instantanée</h3>
            <p>Grille compliance v2, score sur 100 et axes d'amélioration.</p>
          </div>
          <div class="lc-card">
            <h3>🎭 Deux modes</h3>
            <p>Vous agent ou vous prospect — l'IA complète la simulation.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
