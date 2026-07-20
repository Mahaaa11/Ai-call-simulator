"""Lead & Connect brand theme — navy + amber/orange palette."""

from __future__ import annotations

# Brand palette (from leadconnect.fr)
NAVY = "#00234E"
NAVY_DARK = "#001833"
NAVY_MID = "#003D7A"
ORANGE = "#D98328"
ORANGE_DARK = "#B86A1A"
ORANGE_LIGHT = "#E8A04E"
WHITE = "#FFFFFF"
TEXT_MAIN = NAVY
TEXT_SECONDARY = "#707070"
TEXT_MUTED = "#A6A6A6"
BORDER = "#E5E7EB"
BORDER_LIGHT = "#F0F0F0"
BG_PAGE = "#FFFFFF"
BG_SUBTLE = "#FAFAFA"
BG_HIGHLIGHT = "#FFF8F0"
BG_TOTAL_ROW = "#FFF4E8"

STATUS_CHART_COLORS = [
    ORANGE,
    NAVY,
    ORANGE_DARK,
    NAVY_MID,
    TEXT_SECONDARY,
    TEXT_MUTED,
    ORANGE_LIGHT,
    "#10B981",
    "#EF4444",
    "#8B5CF6",
    "#06B6D4",
    "#14B8A6",
]

FONT_STACK = "'Segoe UI', system-ui, -apple-system, sans-serif"

GLOBAL_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap');

section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {NAVY} 0%, {NAVY_DARK} 100%) !important;
}}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
    color: {WHITE} !important;
}}
section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.15) !important; }}
section[data-testid="stSidebar"] button[kind="primary"] {{
    background: linear-gradient(135deg, {ORANGE}, {ORANGE_DARK}) !important;
    border: none !important;
    font-weight: 700 !important;
    color: {WHITE} !important;
}}
section[data-testid="stSidebar"] button[kind="primary"]:hover {{
    background: linear-gradient(135deg, {ORANGE_LIGHT}, {ORANGE}) !important;
}}
section[data-testid="stSidebar"] .nav-section {{
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: {ORANGE} !important;
    margin: 18px 0 6px 0;
}}
section[data-testid="stSidebar"] .brand-title {{
    font-size: 1.05rem;
    font-weight: 700;
    color: {WHITE} !important;
    letter-spacing: 0.06em;
    text-align: center;
    margin: 0;
}}
section[data-testid="stSidebar"] .brand-accent {{
    color: {ORANGE} !important;
}}
section[data-testid="stSidebar"] .brand-sub {{
    font-size: 0.72rem;
    color: {TEXT_MUTED} !important;
    text-align: center;
    margin-top: 2px;
}}
[data-testid="stAppViewContainer"] {{
    background: {BG_PAGE} !important;
    font-family: {FONT_STACK};
}}
[data-testid="stMain"] {{ background: transparent !important; }}
.block-container {{ padding-top: 0.5rem !important; max-width: 100% !important; }}
div[data-testid="stMetric"] {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 12px 16px;
    box-shadow: 0 2px 8px rgba(0,35,78,0.06);
}}
div[data-testid="stMetric"] label {{
    color: {TEXT_SECONDARY} !important;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    color: {NAVY} !important;
}}
.stTabs [data-baseweb="tab"] {{
    color: {TEXT_SECONDARY} !important;
}}
.stTabs [aria-selected="true"] {{
    color: {NAVY} !important;
    border-bottom-color: {ORANGE} !important;
}}
</style>
"""

OVERVIEW_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: {FONT_STACK};
    background: transparent;
    color: {TEXT_MAIN};
    padding: 8px 4px 24px 4px;
}}
.wrap {{ max-width: 1400px; margin: 0 auto; }}
.hero {{
    display: flex; justify-content: space-between; align-items: flex-end;
    padding-bottom: 18px; margin-bottom: 20px;
    border-bottom: 2px solid {BORDER};
}}
.hero h1 {{
    font-size: 1.65rem; font-weight: 700; color: {NAVY};
    letter-spacing: 0.04em;
}}
.hero p {{ font-size: 0.85rem; color: {TEXT_SECONDARY}; margin-top: 6px; }}
.badge {{
    background: {WHITE}; border: 1px solid {BORDER}; border-radius: 20px;
    padding: 8px 16px; font-size: 0.78rem; color: {TEXT_SECONDARY};
    box-shadow: 0 2px 8px rgba(0,35,78,0.06);
}}
.kpi-grid {{
    display: grid; grid-template-columns: repeat(6, 1fr);
    gap: 14px; margin-bottom: 22px;
}}
.kpi {{
    background: {WHITE}; border-radius: 14px; padding: 16px 18px;
    box-shadow: 0 6px 20px rgba(0,35,78,0.07);
    border: 1px solid {BORDER_LIGHT}; position: relative; overflow: hidden;
}}
.kpi::before {{
    content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
}}
.kpi.b::before {{ background: {ORANGE}; }}
.kpi.g::before {{ background: #10B981; }}
.kpi.o::before {{ background: {ORANGE_LIGHT}; }}
.kpi.p::before {{ background: {NAVY_MID}; }}
.kpi.r::before {{ background: #EF4444; }}
.kpi.s::before {{ background: {TEXT_MUTED}; }}
.kpi-label {{
    font-size: 0.64rem; font-weight: 700; color: {TEXT_MUTED};
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px;
}}
.kpi-val {{
    font-size: 1.55rem; font-weight: 700; color: {NAVY}; line-height: 1.1;
}}
.kpi-sub {{ font-size: 0.74rem; color: {TEXT_SECONDARY}; margin-top: 6px; }}
.panels {{ display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 18px; margin-bottom: 18px; }}
.panel {{
    background: {WHITE}; border-radius: 16px; padding: 20px;
    box-shadow: 0 6px 22px rgba(0,35,78,0.07); border: 1px solid {BORDER_LIGHT};
}}
.panel-title {{
    font-size: 0.8rem; font-weight: 700; color: {NAVY};
    text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 14px;
}}
.store-grid {{
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
}}
.store-item {{
    background: {BG_SUBTLE}; border: 1px solid {BORDER}; border-radius: 10px;
    padding: 12px; text-align: center;
}}
.store-item .v {{ font-size: 1.2rem; font-weight: 700; color: {NAVY}; }}
.store-item .l {{ font-size: 0.68rem; color: {TEXT_SECONDARY}; margin-top: 4px; }}
.modules {{
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
}}
.mod {{
    background: linear-gradient(145deg, {WHITE}, {BG_SUBTLE});
    border: 1px solid {BORDER}; border-radius: 12px; padding: 16px;
}}
.mod h3 {{ font-size: 0.82rem; color: {NAVY}; margin-bottom: 6px; }}
.mod p {{ font-size: 0.74rem; color: {TEXT_SECONDARY}; line-height: 1.4; }}
.color-bars {{ display: flex; flex-direction: column; gap: 8px; }}
.color-row {{ display: flex; align-items: center; gap: 10px; font-size: 0.78rem; }}
.color-row .bar {{
    flex: 1; height: 8px; background: {BORDER}; border-radius: 4px; overflow: hidden;
}}
.color-row .fill {{ height: 100%; border-radius: 4px; }}
.dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
@media (max-width: 1100px) {{
    .kpi-grid {{ grid-template-columns: repeat(3, 1fr); }}
    .panels {{ grid-template-columns: 1fr; }}
    .modules {{ grid-template-columns: 1fr; }}
}}
"""

DATA_CLIENT_PAGE_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: {FONT_STACK};
    background: {BG_PAGE};
    color: {TEXT_MAIN};
    padding: 20px 24px 32px 24px;
}}
.wrap {{ max-width: 1380px; margin: 0 auto; }}

.hero {{
    display: flex; justify-content: space-between; align-items: flex-end;
    padding-bottom: 18px; margin-bottom: 20px;
    border-bottom: 2px solid {BORDER};
}}
.hero h1 {{
    font-size: 1.55rem; font-weight: 700; color: {NAVY};
    letter-spacing: 0.06em; text-transform: uppercase;
}}
.hero p {{ font-size: 0.82rem; color: {TEXT_SECONDARY}; margin-top: 5px; }}
.badge {{
    background: {WHITE}; border: 1px solid {BORDER}; border-radius: 20px;
    padding: 8px 16px; font-size: 0.78rem; color: {TEXT_SECONDARY};
    box-shadow: 0 2px 8px rgba(0,35,78,0.06);
}}

.kpi-grid {{
    display: grid; grid-template-columns: repeat(5, 1fr);
    gap: 16px; margin-bottom: 24px;
}}
.kpi {{
    background: {WHITE}; border-radius: 14px; padding: 18px 20px;
    box-shadow: 0 6px 20px rgba(0,35,78,0.07);
    border: 1px solid {BORDER_LIGHT};
    position: relative; overflow: hidden;
}}
.kpi::before {{
    content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
}}
.kpi.b::before {{ background: linear-gradient(180deg,{ORANGE},{ORANGE_DARK}); }}
.kpi.p::before {{ background: linear-gradient(180deg,{NAVY_MID},{NAVY}); }}
.kpi.g::before {{ background: linear-gradient(180deg,#10B981,#059669); }}
.kpi.o::before {{ background: linear-gradient(180deg,{ORANGE_LIGHT},{ORANGE}); }}
.kpi.s::before {{ background: linear-gradient(180deg,{TEXT_MUTED},{TEXT_SECONDARY}); }}
.kpi-label {{
    font-size: 0.68rem; font-weight: 700; color: {TEXT_MUTED};
    text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;
}}
.kpi-val {{
    font-size: 2rem; font-weight: 700; color: {NAVY};
    line-height: 1; letter-spacing: -0.03em;
}}
.kpi-pct {{ font-size: 0.9rem; font-weight: 600; color: {TEXT_SECONDARY}; }}
.kpi-desc {{ font-size: 0.74rem; color: {TEXT_MUTED}; margin-top: 8px; line-height: 1.35; }}

.panels {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 22px; }}
.panel {{
    background: {WHITE}; border-radius: 16px; padding: 22px;
    box-shadow: 0 6px 22px rgba(0,35,78,0.07);
    border: 1px solid {BORDER_LIGHT};
}}
.panel-head {{
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid {BORDER_LIGHT};
}}
.panel-num {{
    background: {NAVY}; color: {WHITE}; font-size: 0.72rem; font-weight: 700;
    width: 26px; height: 26px; border-radius: 7px;
    display: flex; align-items: center; justify-content: center;
}}
.panel-title {{
    font-size: 0.82rem; font-weight: 700; color: {NAVY};
    text-transform: uppercase; letter-spacing: 0.05em;
}}
.panel-body {{ display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 14px; align-items: start; }}

table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
th {{
    text-align: left; padding: 9px 10px; background: {BG_SUBTLE};
    color: {TEXT_SECONDARY}; font-size: 0.68rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.05em;
    border-bottom: 2px solid {BORDER};
}}
td {{ padding: 9px 10px; border-bottom: 1px solid {BORDER_LIGHT}; }}
tr:hover td {{ background: {BG_SUBTLE}; }}
tr.total td {{
    font-weight: 700; background: {BG_TOTAL_ROW}; color: {NAVY};
    border-top: 2px solid {ORANGE};
}}
.dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 7px; vertical-align: middle; }}
.pct-wrap {{ display: flex; align-items: center; gap: 7px; }}
.pct-bar {{ flex: 1; height: 6px; background: {BORDER}; border-radius: 3px; max-width: 72px; overflow: hidden; }}
.pct-fill {{ height: 100%; background: linear-gradient(90deg,{ORANGE},{ORANGE_LIGHT}); border-radius: 3px; }}
.chart-box {{ background: {BG_SUBTLE}; border-radius: 12px; border: 1px solid {BORDER_LIGHT}; padding: 4px; min-height: 280px; }}

.chain-panel {{
    background: linear-gradient(135deg, {WHITE}, {BG_SUBTLE});
    border-radius: 16px; padding: 24px 28px; margin-bottom: 18px;
    box-shadow: 0 6px 22px rgba(0,35,78,0.07); border: 1px solid {BORDER_LIGHT};
}}
.chain-title {{ font-size: 0.92rem; font-weight: 700; color: {NAVY}; text-transform: uppercase; letter-spacing: 0.05em; }}
.chain-sub {{ font-size: 0.78rem; color: {TEXT_SECONDARY}; margin: 5px 0 18px 0; }}
.chain-flow {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; justify-content: center; }}
.chain-box {{
    background: {WHITE}; border: 1px solid {BORDER}; border-radius: 12px;
    padding: 14px 16px; text-align: center; min-width: 115px;
    box-shadow: 0 2px 8px rgba(0,35,78,0.05);
}}
.chain-box.end {{
    background: linear-gradient(145deg,{BG_HIGHLIGHT},{BG_TOTAL_ROW});
    border: 2px solid {ORANGE}; box-shadow: 0 4px 16px rgba(217,131,40,0.22);
}}
.chain-box .v {{ font-size: 1.3rem; font-weight: 700; color: {NAVY}; }}
.chain-box.end .v {{ color: {ORANGE_DARK}; }}
.chain-box .l {{ font-size: 0.66rem; color: {TEXT_SECONDARY}; margin-top: 4px; line-height: 1.3; }}
.chain-op {{ font-size: 1.4rem; color: {TEXT_MUTED}; font-weight: 300; padding: 0 4px; }}
.chain-op.minus {{ color: #EF4444; font-weight: 700; }}

.footer {{
    display: flex; justify-content: space-between; padding-top: 14px;
    font-size: 0.72rem; color: {TEXT_MUTED}; border-top: 1px solid {BORDER};
}}

.panels-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 22px; }}
@media (max-width: 1100px) {{ .panels-3 {{ grid-template-columns: 1fr; }} }}
"""
