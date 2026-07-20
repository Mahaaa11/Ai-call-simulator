"""Cross-module analytics for the unified overview dashboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from engine import data_client_dashboard, dashboard


def compute_overview_metrics(
    df_db: pd.DataFrame,
    df_hist: pd.DataFrame,
    *,
    year: int | None = None,
    stale_days: int = 60,
    retry_days: int = 90,
    store_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate KPIs from Data Client and Performance modules."""
    year = year or datetime.now().year
    dc = data_client_dashboard.compute_data_client_dashboard(
        df_db,
        df_hist,
        year=year,
    )
    perf = dashboard.compute_dashboard(
        df_db,
        df_hist,
        stale_days=stale_days,
        retry_days=retry_days,
    )
    vente = perf.get("vente_conversion", {})
    buckets = perf.get("contacts_by_bucket", {})
    stale = perf.get("stale_contacts", {})
    conversion = perf.get("conversion", {})

    color_df = dc.get("color_distribution", pd.DataFrame())
    status_df = dc.get("status_distribution", pd.DataFrame())
    top_colors = []
    if not color_df.empty:
        for _, row in color_df.head(4).iterrows():
            if int(row.get("Nombre de Lead", 0)) > 0:
                top_colors.append(
                    {
                        "label": row["Couleur"],
                        "count": int(row["Nombre de Lead"]),
                        "pct": float(row["% de la Data Client"]),
                    }
                )

    ventes_by_day = vente.get("ventes_by_day", pd.DataFrame())
    recent_ventes = 0
    if not ventes_by_day.empty and "Ventes" in ventes_by_day.columns:
        recent_ventes = int(ventes_by_day.tail(7)["Ventes"].sum())

    return {
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "year": year,
        "store": store_stats or {},
        "total_fiches": int(dc.get("total_fiches", 0)),
        "inactive_count": int(dc.get("inactive_count", 0)),
        "inactive_pct": float(dc.get("inactive_pct", 0)),
        "ventes_year_count": int(dc.get("ventes_year_count", 0)),
        "ventes_year_pct": float(dc.get("ventes_year_pct", 0)),
        "exploitable_count": int(dc.get("exploitable_count", 0)),
        "exploitable_pct": float(dc.get("exploitable_pct", 0)),
        "active_contacts": int(buckets.get("total_contacts", 0)),
        "total_ventes": int(vente.get("total_ventes", 0)),
        "vente_unique_tels": int(vente.get("ventes_unique_tels", 0)),
        "vente_rate_pct": float(vente.get("overall_vente_rate_pct", 0)),
        "recent_ventes_7d": recent_ventes,
        "stale_count": int(stale.get("stale_count", 0)),
        "stale_pct": float(stale.get("stale_pct", 0)),
        "recyclable_count": int(stale.get("recyclable_count", 0)),
        "positive_rate_pct": float(conversion.get("positive_rate_pct", 0))
        if conversion.get("available")
        else None,
        "top_colors": top_colors,
        "status_count": int(len(status_df[status_df["Nombre de Lead"] > 0]))
        if not status_df.empty
        else 0,
        "chain": dc.get("exploitable_chain", []),
    }
