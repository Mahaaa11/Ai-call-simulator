"""Métriques de performance pour le tableau de bord recyclage."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd

from engine.processor import (
    DATE_ALIASES,
    DEFAULT_STATUS_MAPPING,
    STATUS_ALIASES,
    TEL_ALIASES,
    _assign_color,
    _clean_tel_db,
    _clean_tel_hist_initial,
    _find_column,
    _map_status,
    _normalize_columns,
    _parse_date_column,
    process_data,
)
from engine.status_labels import apply_resolved_status_labels

_COLOR_DISPLAY: dict[str, str] = {
    "Green": "Vert",
    "Blue": "Bleu",
    "Orange": "Orange",
    "Red": "Rouge",
    "Unknown": "Noir",
}


def _color_to_display(series: pd.Series) -> pd.Series:
    return series.astype(str).map(lambda c: _COLOR_DISPLAY.get(c, "Noir")).fillna("Noir")


COLOR_LABELS_FR: dict[str, str] = {
    "Green": "Vert (>60 j)",
    "Blue": "Bleu (39-60 j)",
    "Orange": "Orange (15-38 j)",
    "Red": "Rouge (<15 j)",
    "Unknown": "Inconnu",
}

COLOR_ORDER = ["Green", "Blue", "Orange", "Red", "Unknown"]

POSITIVE_STATUSES = {"Rappel Personnel", "A Relancer"}
NEGATIVE_STATUSES = {"Refus", "Ne jamais appeler", "Hors cible", "Pas de collaboration"}
RECYCLABLE_STATUSES = {
    label
    for label in DEFAULT_STATUS_MAPPING.values()
    if label not in NEGATIVE_STATUSES
}

SALE_STATUS_CODE = "1"
SALE_STATUS_LABEL = "Vente"

EXTENDED_STATUS_MAPPING: dict[int, str] = {
    **DEFAULT_STATUS_MAPPING,
    1: SALE_STATUS_LABEL,
}


def _status_code_series(series: pd.Series) -> pd.Series:
    codes = pd.to_numeric(series, errors="coerce")
    out = pd.Series(index=series.index, dtype=str)
    out[codes.notna()] = codes[codes.notna()].astype(int).astype(str)
    out[codes.isna()] = series.astype(str).str.strip()
    return out


def _apply_status_labels(hist: pd.DataFrame, status_mapping: dict[int, str]) -> pd.Series:
    return apply_resolved_status_labels(hist, status_mapping=status_mapping).fillna("Autre")


def _sort_history_chronologically(hist: pd.DataFrame) -> pd.DataFrame:
    out = hist.copy()
    if "HEURE" in out.columns:
        hours = pd.to_numeric(out["HEURE"], errors="coerce").fillna(0).astype(int).astype(str).str.zfill(4)
        hours = hours.str[:2] + ":" + hours.str[2:]
        out["_DATETIME"] = pd.to_datetime(
            out["DATE"].dt.strftime("%Y-%m-%d") + " " + hours,
            errors="coerce",
        )
        out["_DATETIME"] = out["_DATETIME"].fillna(out["DATE"])
    else:
        out["_DATETIME"] = out["DATE"]
    return out.sort_values(["TEL", "_DATETIME", "DATE"]).reset_index(drop=True)


def _compute_status_transitions(hist: pd.DataFrame) -> pd.DataFrame:
    if hist.empty:
        return pd.DataFrame(
            columns=[
                "TEL",
                "DATE",
                "STATUS_CODE",
                "Status_Category",
                "Prior_Status_Code",
                "Prior_Status",
            ]
        )

    ordered = _sort_history_chronologically(hist)
    ordered["STATUS_CODE"] = _status_code_series(ordered["STATUS"])
    ordered["Prior_Status_Code"] = ordered.groupby("TEL")["STATUS_CODE"].shift(1)
    ordered["Prior_Status"] = ordered.groupby("TEL")["Status_Category"].shift(1)
    ordered["Prior_Status_Label"] = ordered.groupby("TEL")["Status_Label"].shift(1)
    for src, dst in (
        ("LIB_DETAIL", "Prior_LIB_DETAIL"),
        ("STATUS_STATUS", "Prior_STATUS_STATUS"),
        ("LIB_STATUS", "Prior_LIB_STATUS"),
    ):
        if src in ordered.columns:
            ordered[dst] = ordered.groupby("TEL")[src].shift(1)
    if "Color" in ordered.columns:
        ordered["Prior_Color"] = ordered.groupby("TEL")["Color"].shift(1)
        ordered["Prior_Color_Display"] = _color_to_display(ordered["Prior_Color"].fillna("Unknown"))
    transitions = ordered[ordered["Prior_Status"].notna()].copy()
    return transitions.reset_index(drop=True)


def _compute_vente_conversion(transitions: pd.DataFrame, hist: pd.DataFrame) -> dict[str, Any]:
    empty_daily = pd.DataFrame(columns=["Date", "Ventes", "Appels", "Taux_Vente_%"])
    empty_prior = pd.DataFrame(
        columns=["Statut_précédent", "Ventes", "Transitions_depuis_statut", "Taux_conversion_%"]
    )
    empty_matrix = pd.DataFrame(columns=["Statut_précédent", "Statut_résultat", "Transitions"])

    if hist.empty:
        return {
            "total_ventes": 0,
            "ventes_unique_tels": 0,
            "overall_vente_rate_pct": 0.0,
            "ventes_by_day": pd.DataFrame(columns=["Date", "Ventes"]),
            "daily_outcomes": pd.DataFrame(columns=["Date", "Statut", "Appels"]),
            "daily_conversion": empty_daily,
            "conversion_by_prior_status": empty_prior,
            "transition_matrix": empty_matrix,
            "vente_transitions": pd.DataFrame(),
        }

    vente_rows = hist[_status_code_series(hist["STATUS"]) == SALE_STATUS_CODE].copy()
    total_ventes = len(vente_rows)
    ventes_unique_tels = int(vente_rows["TEL"].nunique()) if not vente_rows.empty else 0
    unique_tels = int(hist["TEL"].nunique())
    overall_rate = round(100 * ventes_unique_tels / unique_tels, 2) if unique_tels else 0.0

    ventes_by_day = (
        vente_rows.groupby(vente_rows["DATE"].dt.date)
        .size()
        .reset_index(name="Ventes")
        .rename(columns={"DATE": "Date"})
        if not vente_rows.empty
        else pd.DataFrame(columns=["Date", "Ventes"])
    )

    daily_outcomes = (
        hist.groupby([hist["DATE"].dt.date, "Status_Category"])
        .size()
        .reset_index(name="Appels")
        .rename(columns={"DATE": "Date", "Status_Category": "Statut"})
        .sort_values(["Date", "Appels"], ascending=[True, False])
    )

    daily_totals = (
        hist.groupby(hist["DATE"].dt.date)
        .size()
        .reset_index(name="Appels")
        .rename(columns={"DATE": "Date"})
    )
    daily_conversion = daily_totals.merge(ventes_by_day, on="Date", how="left")
    daily_conversion["Ventes"] = daily_conversion["Ventes"].fillna(0).astype(int)
    daily_conversion["Taux_Vente_%"] = (
        (100 * daily_conversion["Ventes"] / daily_conversion["Appels"])
        .replace([float("inf"), -float("inf")], 0)
        .fillna(0)
        .round(2)
    )

    if transitions.empty:
        return {
            "total_ventes": total_ventes,
            "ventes_unique_tels": ventes_unique_tels,
            "overall_vente_rate_pct": overall_rate,
            "ventes_by_day": ventes_by_day,
            "daily_outcomes": daily_outcomes,
            "daily_conversion": daily_conversion,
            "conversion_by_prior_status": empty_prior,
            "transition_matrix": empty_matrix,
            "vente_transitions": pd.DataFrame(),
        }

    transition_matrix = (
        transitions.groupby(["Prior_Status", "Status_Category"], dropna=False)
        .size()
        .reset_index(name="Transitions")
        .rename(columns={"Prior_Status": "Statut_précédent", "Status_Category": "Statut_résultat"})
        .sort_values("Transitions", ascending=False)
    )

    vente_transitions = transitions[
        _status_code_series(transitions["STATUS"]) == SALE_STATUS_CODE
    ].copy()

    totals_from_prior = (
        transitions.groupby("Prior_Status", dropna=False)
        .size()
        .rename("Transitions_depuis_statut")
        .reset_index()
        .rename(columns={"Prior_Status": "Statut_précédent"})
    )
    ventes_from_prior = (
        vente_transitions.groupby("Prior_Status", dropna=False)
        .size()
        .rename("Ventes")
        .reset_index()
        .rename(columns={"Prior_Status": "Statut_précédent"})
    )
    conversion_by_prior = totals_from_prior.merge(ventes_from_prior, on="Statut_précédent", how="left")
    conversion_by_prior["Ventes"] = conversion_by_prior["Ventes"].fillna(0).astype(int)
    conversion_by_prior["Taux_conversion_%"] = (
        (100 * conversion_by_prior["Ventes"] / conversion_by_prior["Transitions_depuis_statut"])
        .replace([float("inf"), -float("inf")], 0)
        .fillna(0)
        .round(2)
    )
    conversion_by_prior = conversion_by_prior.sort_values(
        ["Ventes", "Taux_conversion_%"], ascending=[False, False]
    )

    return {
        "total_ventes": total_ventes,
        "ventes_unique_tels": ventes_unique_tels,
        "overall_vente_rate_pct": overall_rate,
        "ventes_by_day": ventes_by_day,
        "daily_outcomes": daily_outcomes,
        "daily_conversion": daily_conversion.sort_values("Date"),
        "conversion_by_prior_status": conversion_by_prior,
        "transition_matrix": transition_matrix,
        "vente_transitions": vente_transitions,
    }


def _prepare_history_frame(
    df_hist: pd.DataFrame,
    df_db: pd.DataFrame,
    *,
    status_mapping: dict[int, str] | None = None,
) -> pd.DataFrame:
    status_mapping = status_mapping or EXTENDED_STATUS_MAPPING
    hist = _normalize_columns(df_hist.copy())
    db = _normalize_columns(df_db.copy())

    hist_tel_col = _find_column(hist, TEL_ALIASES)
    hist_status_col = _find_column(hist, STATUS_ALIASES)
    hist_date_col = _find_column(hist, DATE_ALIASES)
    db_tel_col = _find_column(db, TEL_ALIASES)

    if not all([hist_tel_col, hist_status_col, hist_date_col, db_tel_col]):
        return pd.DataFrame()

    hist = hist.rename(
        columns={
            hist_tel_col: "TEL",
            hist_status_col: "STATUS",
            hist_date_col: "DATE",
        }
    )
    db = db.rename(columns={db_tel_col: "TEL"})
    db["TEL"] = _clean_tel_db(db["TEL"])
    hist["TEL_cleaned_initial"] = _clean_tel_hist_initial(hist["TEL"])
    hist["TEL"] = hist["TEL_cleaned_initial"]

    db_tels = set(db["TEL"].dropna().unique())
    hist = hist[hist["TEL"].isin(db_tels)].copy()
    hist["DATE"] = _parse_date_column(hist["DATE"])
    hist = hist[hist["DATE"].notna()].copy()
    hist["Status_Category"] = _apply_status_labels(hist, status_mapping)
    hist["Status_Label"] = apply_resolved_status_labels(hist, status_mapping=status_mapping)
    hist["Color"] = (pd.Timestamp.today().normalize() - hist["DATE"]).dt.days.apply(_assign_color)
    return hist.reset_index(drop=True)


def _duplicate_key_columns(df: pd.DataFrame) -> list[str]:
    cols = ["TEL", "DATE", "STATUS"]
    if "HEURE" in df.columns:
        cols.append("HEURE")
    return [col for col in cols if col in df.columns]


def compute_dashboard(
    df_db: pd.DataFrame,
    df_hist: pd.DataFrame,
    *,
    stale_days: int = 60,
    retry_days: int = 90,
    status_mapping: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Calcule toutes les métriques du tableau de bord."""
    status_mapping = status_mapping or EXTENDED_STATUS_MAPPING
    latest, pipeline_stats = process_data(
        df_db=df_db,
        df_hist=df_hist,
        status_mapping=status_mapping,
        return_stats=True,
    )
    hist = _prepare_history_frame(df_hist, df_db, status_mapping=status_mapping)

    db = _normalize_columns(df_db.copy())
    db_tel_col = _find_column(db, TEL_ALIASES)
    if db_tel_col:
        db = db.rename(columns={db_tel_col: "TEL"})
        db["TEL"] = _clean_tel_db(db["TEL"])

    metrics: dict[str, Any] = {
        "pipeline": pipeline_stats,
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
    }

    # --- Contacts par bucket (couleur) ---
    if not latest.empty:
        by_color = (
            latest["Color"]
            .value_counts()
            .reindex(COLOR_ORDER, fill_value=0)
            .astype(int)
            .to_dict()
        )
        by_color_fr = {
            COLOR_LABELS_FR.get(color, color): count for color, count in by_color.items()
        }
        by_status_color = (
            latest.groupby(["Status_Category", "Color"], dropna=False)
            .size()
            .reset_index(name="Contacts")
            .sort_values(["Status_Category", "Color"])
        )
        by_status_color["Couleur"] = by_status_color["Color"].map(
            lambda c: COLOR_LABELS_FR.get(c, c)
        )
    else:
        by_color = {color: 0 for color in COLOR_ORDER}
        by_color_fr = {COLOR_LABELS_FR.get(color, color): 0 for color in COLOR_ORDER}
        by_status_color = pd.DataFrame(columns=["Status_Category", "Color", "Contacts", "Couleur"])

    metrics["contacts_by_bucket"] = {
        "by_color": by_color,
        "by_color_fr": by_color_fr,
        "by_status_color": by_status_color,
        "total_contacts": int(len(latest)),
    }

    # --- Contacts obsolètes ---
    if not latest.empty:
        stale_mask = latest["Days_Since_Last_Call"] >= stale_days
        very_stale_mask = latest["Days_Since_Last_Call"] >= 90
        recyclable_mask = (
            latest["Color"].isin(["Green", "Blue"])
            & latest["Status_Category"].isin(RECYCLABLE_STATUSES)
        )
        stale_df = latest[stale_mask].copy()
    else:
        stale_mask = pd.Series(dtype=bool)
        very_stale_mask = pd.Series(dtype=bool)
        recyclable_mask = pd.Series(dtype=bool)
        stale_df = latest.copy()

    metrics["stale_contacts"] = {
        "threshold_days": stale_days,
        "stale_count": int(stale_mask.sum()) if not latest.empty else 0,
        "very_stale_count": int(very_stale_mask.sum()) if not latest.empty else 0,
        "recyclable_count": int(recyclable_mask.sum()) if not latest.empty else 0,
        "stale_pct": round(100 * stale_mask.sum() / len(latest), 1) if len(latest) else 0.0,
        "by_status": (
            stale_df["Status_Category"].value_counts().to_dict() if not stale_df.empty else {}
        ),
        "by_color": (
            stale_df["Color"].value_counts().reindex(COLOR_ORDER, fill_value=0).astype(int).to_dict()
            if not stale_df.empty
            else {color: 0 for color in COLOR_ORDER}
        ),
    }

    # --- Doublons ---
    db_dup_tels = 0
    db_dup_rows = 0
    if db_tel_col and not db.empty:
        tel_counts = db["TEL"].value_counts()
        db_dup_tels = int((tel_counts > 1).sum())
        db_dup_rows = int(tel_counts[tel_counts > 1].sum() - db_dup_tels)

    hist_dup_rows = 0
    if not hist.empty:
        dedupe_cols = _duplicate_key_columns(hist)
        hist_dup_rows = int(hist.duplicated(subset=dedupe_cols, keep=False).sum())

    metrics["duplicates"] = {
        "db_duplicate_tels": db_dup_tels,
        "db_extra_rows": db_dup_rows,
        "history_duplicate_rows": hist_dup_rows,
        "history_total_rows": len(hist),
    }

    # --- Volume de relances par date ---
    retry_df = pd.DataFrame()
    if not hist.empty:
        cutoff = pd.Timestamp.today().normalize() - timedelta(days=retry_days)
        retry_df = hist[hist["DATE"] >= cutoff].copy()
        retry_by_date = (
            retry_df.groupby(retry_df["DATE"].dt.date)
            .size()
            .reset_index(name="Appels")
            .rename(columns={"DATE": "Date"})
        )
        retry_by_date_status = (
            retry_df.groupby([retry_df["DATE"].dt.date, "Status_Category"])
            .size()
            .reset_index(name="Appels")
            .rename(columns={"DATE": "Date"})
        )
    else:
        retry_by_date = pd.DataFrame(columns=["Date", "Appels"])
        retry_by_date_status = pd.DataFrame(columns=["Date", "Status_Category", "Appels"])

    metrics["retry_volume"] = {
        "window_days": retry_days,
        "total_calls": int(len(retry_df)),
        "by_date": retry_by_date,
        "by_date_status": retry_by_date_status,
        "avg_calls_per_day": round(len(retry_df) / max(retry_days, 1), 1),
    }

    # --- Résultats après recyclage (état actuel + activité récente) ---
    if not latest.empty:
        outcomes_by_status = latest["Status_Category"].value_counts().to_dict()
        outcomes_recyclable = (
            latest[latest["Color"].isin(["Green", "Blue"])]["Status_Category"]
            .value_counts()
            .to_dict()
        )
    else:
        outcomes_by_status = {}
        outcomes_recyclable = {}

    recent_window = 30
    recent_outcomes: dict[str, int] = {}
    if not hist.empty:
        recent_cutoff = pd.Timestamp.today().normalize() - timedelta(days=recent_window)
        recent_hist = hist[hist["DATE"] >= recent_cutoff]
        recent_outcomes = recent_hist["Status_Category"].value_counts().to_dict()

    metrics["outcomes"] = {
        "current_by_status": outcomes_by_status,
        "recyclable_buckets_by_status": outcomes_recyclable,
        "recent_30d_by_status": recent_outcomes,
        "recent_window_days": recent_window,
    }

    # --- Taux de contact positif (si disponible) ---
    conversion_available = not latest.empty
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    positive_rate = 0.0

    if conversion_available:
        status_series = latest["Status_Category"].dropna()
        positive_count = int(status_series.isin(POSITIVE_STATUSES).sum())
        negative_count = int(status_series.isin(NEGATIVE_STATUSES).sum())
        neutral_count = int(len(status_series) - positive_count - negative_count)
        if len(status_series):
            positive_rate = round(100 * positive_count / len(status_series), 1)

    metrics["conversion"] = {
        "available": conversion_available,
        "positive_statuses": sorted(POSITIVE_STATUSES),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "positive_rate_pct": positive_rate,
        "note": (
            "Basé sur le dernier statut connu par TEL. "
            "Le suivi post-campagne pourra affiner ce taux plus tard."
        ),
    }

    transitions = _compute_status_transitions(hist)
    metrics["vente_conversion"] = _compute_vente_conversion(transitions, hist)
    metrics["status_transitions"] = {
        "total_transitions": int(len(transitions)),
        "matrix": metrics["vente_conversion"]["transition_matrix"],
        "top_transitions": (
            metrics["vente_conversion"]["transition_matrix"].head(25)
            if not metrics["vente_conversion"]["transition_matrix"].empty
            else metrics["vente_conversion"]["transition_matrix"]
        ),
    }

    metrics["latest"] = latest
    metrics["history"] = hist
    return metrics
