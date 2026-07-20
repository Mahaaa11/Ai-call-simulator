"""Interface TABLEAU DE BORD – DATA CLIENT — rendu HTML complet."""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from engine.data_client_dashboard import COLOR_DISPLAY_ORDER, COLOR_HEX, color_hex_for_label
from ui.brand_theme import DATA_CLIENT_PAGE_CSS, NAVY, STATUS_CHART_COLORS, TEXT_SECONDARY

PAGE_CSS = DATA_CLIENT_PAGE_CSS


def inject_app_theme() -> None:
    from ui.app_shell import inject_global_theme

    inject_global_theme()


def _fmt(n: int | float) -> str:
    return f"{int(n):,}".replace(",", "\u202f")


def _table_html(
    df: pd.DataFrame,
    label_col: str,
    color_map: dict[str, str] | None = None,
    *,
    pct_col: str = "% de la Data Client",
    pct_header: str = "%",
    extra_pct_col: str | None = None,
    extra_pct_header: str | None = None,
) -> str:
    if df.empty:
        return "<p>Aucune donnée</p>"
    if pct_col not in df.columns:
        pct_col = "% de la Data Client"
    max_pct = float(df[pct_col].max()) or 100
    rows = []
    for _, row in df.iterrows():
        label = str(row[label_col]).strip()
        count = int(row["Nombre de Lead"])
        pct = float(row[pct_col])
        w = min(100, pct / max_pct * 100)
        dot = ""
        bar_inner = f"<div class='pct-fill' style='width:{w}%'></div>"
        if color_map is not None:
            hex_color = color_hex_for_label(label)
            dot = f"<span class='dot' style='background:{hex_color}'></span>"
            bar_inner = (
                f"<div style='height:100%;width:{w}%;background:{hex_color};"
                f"border-radius:3px;'></div>"
            )
        extra_cell = ""
        if extra_pct_col and extra_pct_col in df.columns:
            extra_pct = float(row[extra_pct_col])
            extra_cell = f"<td style='text-align:right'>{extra_pct:.2f}%</td>"
        rows.append(
            f"<tr><td>{dot}<b>{label}</b></td>"
            f"<td style='text-align:right;font-weight:600'>{_fmt(count)}</td>"
            f"<td><div class='pct-wrap'><div class='pct-bar'>"
            f"{bar_inner}</div></div>"
            f"<span>{pct:.2f}%</span></div></td>"
            f"{extra_cell}</tr>"
        )
    total = int(df["Nombre de Lead"].sum())
    tpct = round(float(df[pct_col].sum()), 2)
    extra_total = ""
    if extra_pct_col and extra_pct_col in df.columns:
        extra_total = f"<td style='text-align:right'><b>{round(float(df[extra_pct_col].sum()), 2):.2f}%</b></td>"
    rows.append(
        f"<tr class='total'><td><b>TOTAL</b></td>"
        f"<td style='text-align:right'><b>{_fmt(total)}</b></td>"
        f"<td><b>{tpct:.2f}%</b></td>{extra_total}</tr>"
    )
    extra_th = f"<th>{extra_pct_header}</th>" if extra_pct_col and extra_pct_header else ""
    return (
        "<table><thead><tr>"
        f"<th>{label_col}</th><th style='text-align:right'>Nombre</th><th>{pct_header}</th>"
        f"{extra_th}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _matrix_html(df: pd.DataFrame, color_map: dict[str, str] | None = None) -> str:
    if df.empty:
        return "<p style='color:#94a3b8;font-size:0.82rem'>Aucune donnée pour les filtres sélectionnés.</p>"
    rows = []
    for _, row in df.iterrows():
        color = str(row.get("Couleur", "")).strip()
        dot = ""
        if color_map is not None:
            hex_color = color_hex_for_label(color)
            dot = f"<span class='dot' style='background:{hex_color}'></span>"
        rows.append(
            f"<tr><td><b>{row['Statut']}</b></td>"
            f"<td>{dot}{color}</td>"
            f"<td style='text-align:right;font-weight:600'>{_fmt(int(row['Nombre de Lead']))}</td>"
            f"<td>{float(row['% de la Data Client']):.2f}%</td></tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Statut</th><th>Couleur</th><th style='text-align:right'>Nombre</th><th>%</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def _plotly_figure(labels: list[str], values: list[int], colors: list[str], center: str):
    import plotly.graph_objects as go

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.62,
                marker={"colors": colors, "line": {"color": "#fff", "width": 2}},
                textinfo="none",
                hovertemplate="<b>%{label}</b><br>%{value:,}<br>%{percent}<extra></extra>",
                pull=[0.04] * len(values),
            )
        ]
    )
    fig.update_layout(
        showlegend=True,
        legend={"orientation": "h", "y": -0.12, "x": 0.5, "xanchor": "center", "font": {"size": 10}},
        margin={"t": 10, "b": 36, "l": 4, "r": 4},
        height=290,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[
            {
                "text": f"<b>{center}</b><br><span style='font-size:10px;color:{TEXT_SECONDARY}'>Total</span>",
                "x": 0.5, "y": 0.5, "showarrow": False,
                "font": {"size": 17, "color": NAVY},
            }
        ],
    )
    return fig


def _chain_html(chain: list[dict[str, Any]]) -> str:
    parts = ['<div class="chain-flow">']
    for step in chain:
        op = step.get("op")
        if op and op not in (None, "None") and op != "=":
            parts.append(f"<span class='chain-op minus'>{op}</span>")
        elif op == "=":
            parts.append("<span class='chain-op'>=</span>")
        end = op == "="
        lbl = step["label"]
        if end:
            lbl = f"{step['label']}<br><b>{step['pct']}%</b> de la Data Client"
        cls = "chain-box end" if end else "chain-box"
        parts.append(
            f"<div class='{cls}'><div class='v'>{_fmt(step['value'])}</div>"
            f"<div class='l'>{lbl}</div></div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _build_page_html(metrics: dict[str, Any]) -> str:
    color_df = metrics["color_distribution"]
    status_df = metrics["status_distribution"]
    matrix_df = metrics.get("status_color_matrix", pd.DataFrame())
    active_colors = metrics.get("active_colors", [])
    active_statuses = metrics.get("active_statuses", [])
    color_filter_active = metrics.get("color_filter_active", False)
    color_filter_count = metrics.get("color_filter_count", 0)
    color_filter_label = metrics.get("color_filter_label", "Toutes")
    filter_bits = []
    if color_filter_active:
        filter_bits.append(f"Couleurs: {color_filter_label} ({_fmt(color_filter_count)} fiches)")
    elif active_colors and len(active_colors) < len(COLOR_DISPLAY_ORDER):
        filter_bits.append("Couleurs: " + ", ".join(active_colors))
    if active_statuses:
        filter_bits.append("Statuts: " + ", ".join(active_statuses))
    filter_label = " · ".join(filter_bits) if filter_bits else "Toutes couleurs / statuts"

    if color_filter_active:
        status_pct_col = "% du filtre couleur"
        status_pct_header = f"% ({color_filter_label})"
        status_extra_col = "% de la Data Client"
        status_extra_header = "% total"
        status_subtitle = (
            f"Répartition des statuts parmi les contacts "
            f"<b>{color_filter_label}</b> ({_fmt(color_filter_count)} fiches) — "
            f"cliquez <b>APPLIQUER LES FILTRES</b> dans la barre latérale pour changer la couleur."
        )
    else:
        status_pct_col = "% de la Data Client"
        status_pct_header = "% Data Client"
        status_extra_col = None
        status_extra_header = None
        status_subtitle = (
            "Répartition globale par statut. Sélectionnez une ou plusieurs couleurs "
            "dans la barre latérale pour voir le % de chaque statut dans ce bucket."
        )

    c_labels = color_df[color_df["Nombre de Lead"] > 0]["Couleur"].tolist()
    c_vals = color_df[color_df["Nombre de Lead"] > 0]["Nombre de Lead"].astype(int).tolist()
    c_colors = [color_hex_for_label(l) for l in c_labels]
    color_chart = _plotly_figure(c_labels, c_vals, c_colors, _fmt(sum(c_vals))).to_html(
        full_html=False, include_plotlyjs=False, config={"displayModeBar": False}
    )

    s_df = status_df[status_df["Nombre de Lead"] > 0]
    s_labels = s_df["Statut"].tolist()
    s_vals = s_df["Nombre de Lead"].astype(int).tolist()
    s_colors = STATUS_CHART_COLORS[: len(s_labels)]
    chart_center = _fmt(color_filter_count) if color_filter_active else _fmt(sum(s_vals))
    status_chart = _plotly_figure(s_labels, s_vals, s_colors, chart_center).to_html(
        full_html=False, include_plotlyjs=False, config={"displayModeBar": False}
    )
    status_table = _table_html(
        status_df,
        "Statut",
        pct_col=status_pct_col,
        pct_header=status_pct_header,
        extra_pct_col=status_extra_col,
        extra_pct_header=status_extra_header,
    )

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>{PAGE_CSS}</style>
</head><body><div class="wrap">

<div class="hero">
  <div>
    <h1>Tableau de bord – Data Client</h1>
    <p>Lead &amp; Connect Fès · Gestion de la Data Client</p>
  </div>
  <div class="badge">📅 MAJ {metrics['generated_at']}<br><span style="font-size:0.72rem">{filter_label}</span></div>
</div>

<div class="kpi-grid">
  <div class="kpi b">
    <div class="kpi-label">Total Fiches</div>
    <div class="kpi-val">{_fmt(metrics['total_fiches'])}</div>
    <div class="kpi-desc">Fiches dans la Data Client</div>
  </div>
  <div class="kpi p">
    <div class="kpi-label">Clients Inactifs</div>
    <div class="kpi-val">{_fmt(metrics['inactive_count'])} <span class="kpi-pct">({metrics['inactive_pct']}%)</span></div>
    <div class="kpi-desc">≥10 appels sans changement de statut</div>
  </div>
  <div class="kpi g">
    <div class="kpi-label">Ventes {metrics['year']}</div>
    <div class="kpi-val">{_fmt(metrics['ventes_year_count'])} <span class="kpi-pct">({metrics['ventes_year_pct']}%)</span></div>
    <div class="kpi-desc">Clients vendus cette année</div>
  </div>
  <div class="kpi o">
    <div class="kpi-label">Exploitables</div>
    <div class="kpi-val">{_fmt(metrics['exploitable_count'])} <span class="kpi-pct">({metrics['exploitable_pct']}%)</span></div>
    <div class="kpi-desc">Potentiel fidélisation immédiat</div>
  </div>
  <div class="kpi s">
    <div class="kpi-label">Année</div>
    <div class="kpi-val" style="font-size:1.6rem">{metrics['year']}</div>
    <div class="kpi-desc">Période de référence ventes</div>
  </div>
</div>

<div class="panels">
  <div class="panel">
    <div class="panel-head"><span class="panel-num">4</span><span class="panel-title">Nombre de lead par couleur</span></div>
    <div class="panel-body">
      <div>{_table_html(color_df, "Couleur", COLOR_HEX)}</div>
      <div class="chart-box">{color_chart}</div>
    </div>
  </div>
  <div class="panel">
    <div class="panel-head"><span class="panel-num">5</span><span class="panel-title">Nombre de lead par statut</span></div>
    <div style="font-size:0.78rem;color:{TEXT_SECONDARY};margin:0 0 12px 36px;line-height:1.45">{status_subtitle}</div>
    <div class="panel-body">
      <div>{status_table}</div>
      <div class="chart-box">{status_chart}</div>
    </div>
  </div>
</div>

<div class="panel" style="margin-bottom:22px">
  <div class="panel-head"><span class="panel-num">6</span><span class="panel-title">Statuts par couleur</span></div>
  <div style="font-size:0.78rem;color:{TEXT_SECONDARY};margin-bottom:12px">
    Croisement statut × couleur — filtrez par couleur dans la barre latérale pour voir quels statuts composent chaque bucket.
  </div>
  {_matrix_html(matrix_df, COLOR_HEX)}
</div>

<div class="chain-panel">
  <div class="chain-title">Clients exploitables (potentiel fidélisation)</div>
  <div class="chain-sub">Clients pouvant être injectés immédiatement en production</div>
  {_chain_html(metrics['exploitable_chain'])}
</div>

<div class="footer">
  <span>Lead &amp; Connect Fès – Gestion de la Data Client</span>
  <span>Dernière mise à jour : {metrics['generated_at']}</span>
</div>

</div></body></html>"""


def _build_excel_export(metrics: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "Indicateur": ["Total fiches", "Clients inactifs", f"Ventes {metrics['year']}", "Clients exploitables"],
                "Valeur": [metrics["total_fiches"], metrics["inactive_count"], metrics["ventes_year_count"], metrics["exploitable_count"]],
                "%": [100, metrics["inactive_pct"], metrics["ventes_year_pct"], metrics["exploitable_pct"]],
            }
        ).to_excel(writer, sheet_name="KPIs", index=False)
        metrics["color_distribution"].to_excel(writer, sheet_name="Couleurs", index=False)
        metrics["status_distribution"].to_excel(writer, sheet_name="Statuts", index=False)
        metrics.get("status_color_matrix", pd.DataFrame()).to_excel(
            writer, sheet_name="Statut_x_Couleur", index=False
        )
        pd.DataFrame(metrics["exploitable_chain"]).to_excel(writer, sheet_name="Exploitables", index=False)
    buffer.seek(0)
    return buffer.getvalue()


def render_data_client_board(metrics: dict[str, Any]) -> bytes:
    page_html = _build_page_html(metrics)
    components.html(page_html, height=1480, scrolling=True)
    return _build_excel_export(metrics)
