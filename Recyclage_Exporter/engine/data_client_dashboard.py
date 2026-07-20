"""Métriques TABLEAU DE BORD – DATA CLIENT (Lead & Connect)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from engine.dashboard import (
    EXTENDED_STATUS_MAPPING,
    SALE_STATUS_CODE,
    _apply_status_labels,
    _prepare_history_frame,
    _status_code_series,
)
from engine.processor import (
    TEL_ALIASES,
    _clean_tel_db,
    _find_column,
    _map_status,
    _normalize_columns,
    process_data,
)

# Libellés affichés dans le tableau de bord corporate
COLOR_DISPLAY_ORDER = ["Vert", "Bleu", "Orange", "Rouge", "Noir"]
COLOR_TO_DISPLAY: dict[str, str] = {
    "Green": "Vert",
    "Blue": "Bleu",
    "Orange": "Orange",
    "Red": "Rouge",
    "Unknown": "Noir",
}
DISPLAY_TO_COLOR: dict[str, str] = {v: k for k, v in COLOR_TO_DISPLAY.items()}

COLOR_HEX: dict[str, str] = {
    "Vert": "#4CAF50",
    "Bleu": "#2196F3",
    "Orange": "#FF9800",
    "Rouge": "#F44336",
    "Noir": "#424242",
    # Aliases (legacy / internal keys)
    "Jaune": "#2196F3",
    "Green": "#4CAF50",
    "Blue": "#2196F3",
    "Red": "#F44336",
    "Unknown": "#424242",
}


def color_hex_for_label(label: str) -> str:
    """Resolve display/internal color label to hex (never grey fallback)."""
    key = str(label).strip()
    return COLOR_HEX.get(key, COLOR_HEX["Bleu"])

EXCLUSION_STATUSES = {
    "Ne jamais appeler": "Ne jamais rappeler",
    "Hors cible": "Hors cible",
}

STATUS_DISPLAY_ORDER = [
    "Répondeur",
    "Refus",
    "Hors cible",
    "Pas de collaboration",
    "Ne jamais appeler",
    "Pas décisionnaire",
    "Rappel Personnel",
    "A Relancer",
    "Vente",
    "Absent",
    "Indisponible",
    "Injoignable",
    "Autre",
    "Non classé",
    "Sans historique",
]


def _map_display_color(series: pd.Series) -> pd.Series:
    return series.map(lambda c: COLOR_TO_DISPLAY.get(str(c), "Noir")).fillna("Noir")


def compute_inactive_clients(
    hist: pd.DataFrame,
    *,
    min_calls: int = 10,
) -> tuple[int, set[str]]:
    """Clients contactés N fois ou plus sans changement de statut."""
    if hist.empty or "TEL" not in hist.columns:
        return 0, set()

    grouped = hist.groupby("TEL").agg(
        calls=("TEL", "size"),
        unique_status=("Status_Category", "nunique"),
    )
    inactive = grouped[
        (grouped["calls"] >= min_calls) & (grouped["unique_status"] == 1)
    ]
    tels = {str(t) for t in inactive.index}
    return len(tels), tels


def _ventes_year_tels(
    hist: pd.DataFrame,
    *,
    year: int | None = None,
    month: int | None = None,
) -> set[str]:
    if hist.empty:
        return set()
    ventes = hist[_status_code_series(hist["STATUS"]) == SALE_STATUS_CODE].copy()
    if year is not None:
        ventes = ventes[ventes["DATE"].dt.year == year]
    if month is not None:
        ventes = ventes[ventes["DATE"].dt.month == month]
    return {str(t) for t in ventes["TEL"].dropna().unique()}


def _is_color_filter_active(colors: list[str] | None) -> bool:
    return bool(colors) and len(colors) < len(COLOR_DISPLAY_ORDER)


def _filter_latest(
    latest: pd.DataFrame,
    *,
    colors: list[str] | None = None,
    statuses: list[str] | None = None,
) -> pd.DataFrame:
    if latest.empty:
        return latest
    out = latest.copy()
    if colors:
        allowed = {DISPLAY_TO_COLOR.get(c, c) for c in colors}
        out = out[out["Color"].isin(allowed)].copy()
    if statuses:
        out = out[out["Status_Category"].isin(statuses)].copy()
    return out


def _build_status_color_matrix(df: pd.DataFrame, *, total_fiches: int) -> pd.DataFrame:
    """Croisement statut × couleur pour filtrer les statuts par couleur."""
    if df.empty or "Status_Category" not in df.columns or "Color" not in df.columns:
        return pd.DataFrame(
            columns=["Statut", "Couleur", "Nombre de Lead", "% de la Data Client"]
        )
    display_colors = _map_display_color(df["Color"])
    grouped = (
        df.assign(_Couleur=display_colors)
        .groupby(["Status_Category", "_Couleur"], dropna=False)
        .size()
        .reset_index(name="Nombre de Lead")
        .rename(columns={"Status_Category": "Statut", "_Couleur": "Couleur"})
    )
    grouped["% de la Data Client"] = grouped["Nombre de Lead"].apply(
        lambda n: round(100 * n / total_fiches, 2) if total_fiches else 0.0
    )
    return grouped.sort_values(["Couleur", "Nombre de Lead"], ascending=[True, False])


def _build_all_client_fiches(
    df_db: pd.DataFrame,
    latest: pd.DataFrame,
    *,
    status_mapping: dict[int, str] | None = None,
) -> pd.DataFrame:
    """Toutes les fiches de la Data Client (1 ligne par TEL en base)."""
    status_mapping = status_mapping or EXTENDED_STATUS_MAPPING
    db = _normalize_columns(df_db.copy())
    tel_col = _find_column(db, TEL_ALIASES) or "TEL"
    db = db.rename(columns={tel_col: "TEL"})
    db["TEL"] = _clean_tel_db(db["TEL"])
    base = db[["TEL"]].drop_duplicates("TEL", keep="last")

    if latest.empty:
        out = base.copy()
        out["Color"] = "Unknown"
        out["Status_Category"] = "Sans historique"
        out["Days_Since_Last_Call"] = pd.NA
        return out

    merged = base.merge(latest, on="TEL", how="left", suffixes=("", "_hist"))
    if "LIB_STATUS" in merged.columns:
        lib = merged["LIB_STATUS"].astype(str).str.strip()
        lib = lib.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        merged["Status_Category"] = merged["Status_Category"].fillna(lib)
    merged["Status_Category"] = merged["Status_Category"].fillna("Non classé")
    merged.loc[merged["DATE"].isna(), "Status_Category"] = merged.loc[
        merged["DATE"].isna(), "Status_Category"
    ].replace("Non classé", "Sans historique")
    merged["Color"] = merged["Color"].fillna("Unknown")
    merged["Days_Since_Last_Call"] = merged["Days_Since_Last_Call"].fillna(-1)
    return merged.reset_index(drop=True)


def compute_data_client_dashboard(
    df_db: pd.DataFrame,
    df_hist: pd.DataFrame,
    *,
    year: int | None = None,
    month: int | None = None,
    colors: list[str] | None = None,
    statuses: list[str] | None = None,
    inactive_min_calls: int = 10,
) -> dict[str, Any]:
    """Calcule les KPIs du tableau de bord Data Client."""
    year = year or datetime.now().year
    latest, pipeline_stats = process_data(
        df_db=df_db,
        df_hist=df_hist,
        status_mapping=EXTENDED_STATUS_MAPPING,
        return_stats=True,
        drop_unmapped_status=False,
    )
    hist = _prepare_history_frame(df_hist, df_db, status_mapping=EXTENDED_STATUS_MAPPING)
    all_fiches = _build_all_client_fiches(df_db, latest)
    color_filtered = _filter_latest(all_fiches, colors=colors)
    latest_filtered = _filter_latest(color_filtered, statuses=statuses)
    color_filter_active = _is_color_filter_active(colors)
    color_filter_count = int(len(color_filtered))
    color_filter_label = ", ".join(colors) if color_filter_active and colors else "Toutes"
    status_color_matrix = _build_status_color_matrix(color_filtered, total_fiches=int(len(all_fiches)))

    total_fiches = int(pipeline_stats.get("db_unique_tels", len(all_fiches)))
    inactive_count, inactive_tels = compute_inactive_clients(
        hist, min_calls=inactive_min_calls
    )
    ventes_year_tels = _ventes_year_tels(hist, year=year, month=month)
    ventes_year_count = len(ventes_year_tels)

    if not latest_filtered.empty:
        display_colors = _map_display_color(latest_filtered["Color"])
        color_counts = (
            display_colors.value_counts()
            .reindex(COLOR_DISPLAY_ORDER, fill_value=0)
            .astype(int)
        )
        color_rows = []
        for label in COLOR_DISPLAY_ORDER:
            count = int(color_counts.get(label, 0))
            pct = round(100 * count / total_fiches, 2) if total_fiches else 0.0
            color_rows.append(
                {
                    "Couleur": label,
                    "Nombre de Lead": count,
                    "% de la Data Client": pct,
                }
            )
        color_df = pd.DataFrame(color_rows)

        status_counts = color_filtered["Status_Category"].value_counts()
        status_pool = color_filter_count if color_filter_count else total_fiches
        allowed_statuses = set(statuses) if statuses else None
        status_rows = []
        for status in STATUS_DISPLAY_ORDER:
            count = int(status_counts.get(status, 0))
            if count <= 0:
                continue
            if allowed_statuses and status not in allowed_statuses:
                continue
            status_rows.append(
                {
                    "Statut": status,
                    "Nombre de Lead": count,
                    "% du filtre couleur": round(100 * count / status_pool, 2)
                    if status_pool
                    else 0.0,
                    "% de la Data Client": round(100 * count / total_fiches, 2)
                    if total_fiches
                    else 0.0,
                }
            )
        for status, count in status_counts.items():
            if status in STATUS_DISPLAY_ORDER:
                continue
            count = int(count)
            if allowed_statuses and status not in allowed_statuses:
                continue
            status_rows.append(
                {
                    "Statut": status,
                    "Nombre de Lead": count,
                    "% du filtre couleur": round(100 * count / status_pool, 2)
                    if status_pool
                    else 0.0,
                    "% de la Data Client": round(100 * count / total_fiches, 2)
                    if total_fiches
                    else 0.0,
                }
            )
        status_df = pd.DataFrame(status_rows)
        if not status_df.empty:
            status_df = status_df.sort_values("Nombre de Lead", ascending=False)
    else:
        color_df = pd.DataFrame(
            columns=["Couleur", "Nombre de Lead", "% de la Data Client"]
        )
        status_df = pd.DataFrame(
            columns=[
                "Statut",
                "Nombre de Lead",
                "% du filtre couleur",
                "% de la Data Client",
            ]
        )
        status_total = 0

    ne_jamais_tels = set()
    hors_cible_tels = set()
    if not latest_filtered.empty:
        ne_jamais_tels = {
            str(t)
            for t in latest_filtered.loc[
                latest_filtered["Status_Category"] == "Ne jamais appeler", "TEL"
            ]
        }
        hors_cible_tels = {
            str(t)
            for t in latest_filtered.loc[
                latest_filtered["Status_Category"] == "Hors cible", "TEL"
            ]
        }

    all_tels = {str(t) for t in latest_filtered["TEL"].dropna()} if not latest_filtered.empty else set()
    inactive_in_base = inactive_tels & all_tels
    ventes_in_base = ventes_year_tels & all_tels

    excluded = inactive_in_base | ne_jamais_tels | hors_cible_tels | ventes_in_base
    exploitable_count = len(all_tels - excluded)
    exploitable_pct = round(100 * exploitable_count / total_fiches, 2) if total_fiches else 0.0

    chain = [
        {
            "label": "Total Data Client",
            "value": total_fiches,
            "pct": 100.0,
            "op": None,
        },
        {
            "label": "Clients inactifs",
            "value": len(inactive_in_base),
            "pct": round(100 * len(inactive_in_base) / total_fiches, 2) if total_fiches else 0.0,
            "op": "−",
            "detail": f"≥{inactive_min_calls} appels sans changement de statut",
        },
        {
            "label": "Ne jamais rappeler",
            "value": len(ne_jamais_tels),
            "pct": round(100 * len(ne_jamais_tels) / total_fiches, 2) if total_fiches else 0.0,
            "op": "−",
        },
        {
            "label": "Hors cible",
            "value": len(hors_cible_tels),
            "pct": round(100 * len(hors_cible_tels) / total_fiches, 2) if total_fiches else 0.0,
            "op": "−",
        },
        {
            "label": f"Déjà vendus en {year}",
            "value": len(ventes_in_base),
            "pct": round(100 * len(ventes_in_base) / total_fiches, 2) if total_fiches else 0.0,
            "op": "−",
        },
        {
            "label": "Clients exploitables",
            "value": exploitable_count,
            "pct": exploitable_pct,
            "op": "=",
        },
    ]

    return {
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "year": year,
        "month": month,
        "total_fiches": total_fiches,
        "inactive_count": len(inactive_in_base),
        "inactive_pct": round(100 * len(inactive_in_base) / total_fiches, 2) if total_fiches else 0.0,
        "ventes_year_count": len(ventes_in_base),
        "ventes_year_pct": round(100 * len(ventes_in_base) / total_fiches, 2) if total_fiches else 0.0,
        "color_distribution": color_df,
        "status_distribution": status_df,
        "status_color_matrix": status_color_matrix,
        "color_filter_active": color_filter_active,
        "color_filter_count": color_filter_count,
        "color_filter_label": color_filter_label,
        "active_colors": colors or COLOR_DISPLAY_ORDER,
        "active_statuses": statuses or [],
        "status_table_total": int(status_df["Nombre de Lead"].sum()) if not status_df.empty else 0,
        "exploitable_count": exploitable_count,
        "exploitable_pct": exploitable_pct,
        "exploitable_chain": chain,
        "pipeline": pipeline_stats,
        "latest": latest_filtered,
        "all_fiches": all_fiches,
        "history": hist,
        "without_mapped_status": int(pipeline_stats.get("latest_unmapped_status", 0)),
        "without_history": int(total_fiches - pipeline_stats.get("latest_before_status_filter", total_fiches)),
    }
