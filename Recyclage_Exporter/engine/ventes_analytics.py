"""Dedicated ventes analytics — origins, prior status/color, conversion paths."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from engine.dashboard import (
    EXTENDED_STATUS_MAPPING,
    SALE_STATUS_CODE,
    _compute_status_transitions,
    _prepare_history_frame,
    _status_code_series,
)
from engine.status_labels import breakdown_autre_ventes, build_status_code_catalog


def _filter_ventes_period(
    ventes: pd.DataFrame,
    *,
    year: int | None = None,
    month: int | None = None,
) -> pd.DataFrame:
    if ventes.empty:
        return ventes
    out = ventes.copy()
    if year is not None:
        out = out[out["DATE"].dt.year == year]
    if month is not None:
        out = out[out["DATE"].dt.month == month]
    return out


def _conversion_table(
    transitions: pd.DataFrame,
    vente_transitions: pd.DataFrame,
    group_col: str,
    label_col: str,
) -> pd.DataFrame:
    if transitions.empty or group_col not in transitions.columns:
        return pd.DataFrame(
            columns=[label_col, "Ventes", "Transitions", "Taux_conversion_%", "Part_des_ventes_%"]
        )
    totals = (
        transitions.groupby(group_col, dropna=False)
        .size()
        .rename("Transitions")
        .reset_index()
        .rename(columns={group_col: label_col})
    )
    ventes = (
        vente_transitions.groupby(group_col, dropna=False)
        .size()
        .rename("Ventes")
        .reset_index()
        .rename(columns={group_col: label_col})
    )
    merged = totals.merge(ventes, on=label_col, how="left")
    merged["Ventes"] = merged["Ventes"].fillna(0).astype(int)
    merged["Taux_conversion_%"] = (
        (100 * merged["Ventes"] / merged["Transitions"])
        .replace([float("inf"), -float("inf")], 0)
        .fillna(0)
        .round(2)
    )
    total_ventes = int(merged["Ventes"].sum())
    merged["Part_des_ventes_%"] = (
        (100 * merged["Ventes"] / total_ventes).round(2) if total_ventes else 0.0
    )
    return merged.sort_values(["Ventes", "Taux_conversion_%"], ascending=[False, False])


def _filter_prior_statuses(vente_trans: pd.DataFrame, prior_statuses: list[str]) -> pd.DataFrame:
    if vente_trans.empty or not prior_statuses:
        return vente_trans
    mask = pd.Series(False, index=vente_trans.index)
    if "Prior_Status" in vente_trans.columns:
        mask |= vente_trans["Prior_Status"].isin(prior_statuses)
    if "Prior_Status_Label" in vente_trans.columns:
        mask |= vente_trans["Prior_Status_Label"].isin(prior_statuses)
    return vente_trans[mask].copy()


def compute_ventes_analytics(
    df_db: pd.DataFrame,
    df_hist: pd.DataFrame,
    *,
    year: int | None = None,
    month: int | None = None,
    prior_colors: list[str] | None = None,
    prior_statuses: list[str] | None = None,
) -> dict[str, Any]:
    """Analyse complète des ventes et de ce qui y mène (statut/couleur précédents)."""
    year = year or datetime.now().year
    hist = _prepare_history_frame(df_hist, df_db, status_mapping=EXTENDED_STATUS_MAPPING)
    if hist.empty:
        return _empty_result(year=year, month=month)

    transitions = _compute_status_transitions(hist)
    all_vente_trans = transitions[
        _status_code_series(transitions["STATUS"]) == SALE_STATUS_CODE
    ].copy()

    vente_trans = _filter_ventes_period(all_vente_trans, year=year, month=month)
    if vente_trans.empty and (year is not None or month is not None):
        return _empty_result(year=year, month=month)

    if prior_colors:
        vente_trans = vente_trans[vente_trans["Prior_Color_Display"].isin(prior_colors)].copy()

    if prior_statuses:
        vente_trans = _filter_prior_statuses(vente_trans, prior_statuses)

    label_col = "Prior_Status_Label" if "Prior_Status_Label" in transitions.columns else "Prior_Status"

    total_ventes = len(vente_trans)
    unique_tels = int(vente_trans["TEL"].nunique()) if not vente_trans.empty else 0
    unique_tels_hist = int(hist["TEL"].nunique())
    overall_rate = round(100 * unique_tels / unique_tels_hist, 2) if unique_tels_hist else 0.0

    by_day = (
        vente_trans.groupby(vente_trans["DATE"].dt.date)
        .size()
        .reset_index(name="Ventes")
        .rename(columns={"DATE": "Date"})
        .sort_values("Date")
        if not vente_trans.empty
        else pd.DataFrame(columns=["Date", "Ventes"])
    )

    by_prior_status = _conversion_table(transitions, vente_trans, label_col, "Statut_précédent")
    by_prior_status_legacy = _conversion_table(
        transitions, vente_trans, "Prior_Status", "Statut_catégorie"
    )
    by_prior_color = _conversion_table(
        transitions, vente_trans, "Prior_Color_Display", "Couleur_précédente"
    )

    status_color_matrix = pd.DataFrame(
        columns=["Statut_précédent", "Couleur_précédente", "Ventes"]
    )
    if not vente_trans.empty:
        status_color_matrix = (
            vente_trans.groupby([label_col, "Prior_Color_Display"], dropna=False)
            .size()
            .reset_index(name="Ventes")
            .rename(
                columns={
                    label_col: "Statut_précédent",
                    "Prior_Color_Display": "Couleur_précédente",
                }
            )
            .sort_values("Ventes", ascending=False)
        )

    autre_breakdown = breakdown_autre_ventes(vente_trans)
    status_code_catalog = build_status_code_catalog(hist, status_mapping=EXTENDED_STATUS_MAPPING)
    unmapped_catalog = status_code_catalog[status_code_catalog["Dans_mapping"] == "Non"].copy()

    detail_cols = [
        "TEL",
        "DATE",
        "Prior_Status_Code",
        "Prior_Status",
        "Prior_Status_Label",
        "Prior_LIB_DETAIL",
        "Prior_STATUS_STATUS",
        "Prior_Color_Display",
        "Prior_Color",
        "Color",
        "Status_Category",
    ]
    detail = vente_trans[[c for c in detail_cols if c in vente_trans.columns]].copy()
    if not detail.empty:
        detail = detail.rename(
            columns={
                "Prior_Status_Code": "Code_avant_vente",
                "Prior_Status": "Catégorie_avant_vente",
                "Prior_Status_Label": "Libellé_avant_vente",
                "Prior_LIB_DETAIL": "LIB_DETAIL_avant",
                "Prior_STATUS_STATUS": "Sous_statut_avant",
                "Prior_Color_Display": "Couleur_avant_vente",
                "Prior_Color": "Couleur_code_avant",
                "Color": "Couleur_vente",
                "Status_Category": "Statut_vente",
            }
        )
        detail["Date_vente"] = detail["DATE"].dt.strftime("%Y-%m-%d")
        detail = detail.sort_values("DATE", ascending=False)

    unmatched = int((vente_trans["Prior_Status"].isna()).sum()) if not vente_trans.empty else 0
    autre_count = (
        int((vente_trans["Prior_Status"] == "Autre").sum()) if not vente_trans.empty else 0
    )

    return {
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "year": year,
        "month": month,
        "total_ventes": total_ventes,
        "ventes_unique_tels": unique_tels,
        "overall_vente_rate_pct": overall_rate,
        "ventes_sans_statut_precedent": unmatched,
        "ventes_autre_categorie": autre_count,
        "ventes_by_day": by_day,
        "conversion_by_prior_status": by_prior_status,
        "conversion_by_prior_status_legacy": by_prior_status_legacy,
        "conversion_by_prior_color": by_prior_color,
        "status_color_matrix": status_color_matrix,
        "autre_breakdown": autre_breakdown,
        "status_code_catalog": status_code_catalog,
        "unmapped_status_catalog": unmapped_catalog,
        "vente_detail": detail,
        "all_ventes_period": total_ventes,
    }


def _empty_result(*, year: int, month: int | None) -> dict[str, Any]:
    empty_conv = pd.DataFrame(
        columns=["Statut_précédent", "Ventes", "Transitions", "Taux_conversion_%", "Part_des_ventes_%"]
    )
    empty_color = pd.DataFrame(
        columns=["Couleur_précédente", "Ventes", "Transitions", "Taux_conversion_%", "Part_des_ventes_%"]
    )
    empty_autre = pd.DataFrame(
        columns=[
            "Code_STATUS",
            "Libellé_avant_vente",
            "LIB_DETAIL",
            "Sous_statut_STATUS_STATUS",
            "Ventes",
            "Part_%",
        ]
    )
    empty_catalog = pd.DataFrame(
        columns=[
            "Code_STATUS",
            "Libellé_résolu",
            "Dans_mapping",
            "LIB_DETAIL_principal",
            "Occurrences",
        ]
    )
    return {
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "year": year,
        "month": month,
        "total_ventes": 0,
        "ventes_unique_tels": 0,
        "overall_vente_rate_pct": 0.0,
        "ventes_sans_statut_precedent": 0,
        "ventes_autre_categorie": 0,
        "ventes_by_day": pd.DataFrame(columns=["Date", "Ventes"]),
        "conversion_by_prior_status": empty_conv,
        "conversion_by_prior_status_legacy": empty_conv,
        "conversion_by_prior_color": empty_color,
        "status_color_matrix": pd.DataFrame(
            columns=["Statut_précédent", "Couleur_précédente", "Ventes"]
        ),
        "autre_breakdown": empty_autre,
        "status_code_catalog": empty_catalog,
        "unmapped_status_catalog": empty_catalog,
        "vente_detail": pd.DataFrame(),
        "all_ventes_period": 0,
    }
