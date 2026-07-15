"""Suivi quotidien des ventes et statut d'origine recyclage."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, BinaryIO

import pandas as pd

from engine.dashboard import EXTENDED_STATUS_MAPPING, SALE_STATUS_CODE
from engine.processor import (
    STATUS_ALIASES,
    TEL_ALIASES,
    _assign_color,
    _clean_tel_db,
    _find_column,
    _map_status,
    _normalize_columns,
    _parse_date_column,
    _read_excel,
    process_data,
)

NOT_FOUND_LABEL = "NON TROUVÉ"


def _apply_status_label(series: pd.Series, lib_series: pd.Series | None = None) -> pd.Series:
    mapped = _map_status(series, EXTENDED_STATUS_MAPPING)
    if lib_series is not None:
        lib = lib_series.astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        mapped = mapped.fillna(lib)
    return mapped.fillna("Autre")


def baseline_from_client_db(df: pd.DataFrame) -> pd.DataFrame:
    """Build TEL → statut/couleur from a flat client DB or Book2-style file."""
    frame = _normalize_columns(df.copy())
    tel_col = _find_column(frame, TEL_ALIASES) or "TEL"
    status_col = _find_column(frame, STATUS_ALIASES) or "STATUS"
    frame = frame.rename(columns={tel_col: "TEL", status_col: "STATUS"})
    frame["TEL"] = _clean_tel_db(frame["TEL"])
    frame = frame.drop_duplicates("TEL", keep="last")
    frame["Statut"] = _apply_status_label(
        frame["STATUS"],
        frame["LIB_STATUS"] if "LIB_STATUS" in frame.columns else None,
    )
    if "COLOR" in frame.columns:
        frame["Couleur"] = frame["COLOR"]
    elif "Color" in frame.columns:
        frame["Couleur"] = frame["Color"]
    else:
        date_col = next((c for c in frame.columns if c in ("DATE", "DATETIME")), None)
        if date_col:
            dates = _parse_date_column(frame[date_col])
            frame["Couleur"] = (pd.Timestamp.today().normalize() - dates).dt.days.apply(_assign_color)
        else:
            frame["Couleur"] = "Unknown"
    return frame[["TEL", "Statut", "Couleur"]].reset_index(drop=True)


def baseline_from_recyclage_export(source: str | BinaryIO | BytesIO) -> pd.DataFrame:
    """Load multi-sheet Recyclage_Data_Client export (sheet name = statut)."""
    if hasattr(source, "seek"):
        source.seek(0)
    xl = pd.ExcelFile(source)
    parts: list[pd.DataFrame] = []
    for sheet in xl.sheet_names:
        raw = pd.read_excel(source, sheet_name=sheet, header=None)
        if hasattr(source, "seek"):
            source.seek(0)
        header_idx = None
        for i in range(min(10, len(raw))):
            if str(raw.iloc[i, 0]).strip().upper() == "INDICE":
                header_idx = i
                break
        if header_idx is None:
            continue
        df = pd.read_excel(source, sheet_name=sheet, header=header_idx)
        if hasattr(source, "seek"):
            source.seek(0)
        df = _normalize_columns(df)
        tel_col = _find_column(df, TEL_ALIASES) or "TEL"
        if tel_col not in df.columns:
            continue
        part = pd.DataFrame(
            {
                "TEL": _clean_tel_db(df[tel_col]),
                "Statut": sheet,
            }
        )
        if "COLOR" in df.columns:
            part["Couleur"] = df["COLOR"].values
        else:
            part["Couleur"] = "Unknown"
        parts.append(part)
    if not parts:
        return pd.DataFrame(columns=["TEL", "Statut", "Couleur"])
    out = pd.concat(parts, ignore_index=True).drop_duplicates("TEL", keep="first")
    return out.reset_index(drop=True)


def baseline_from_store_latest(df_db: pd.DataFrame, df_hist: pd.DataFrame) -> pd.DataFrame:
    """Derive baseline from processed store (Status_Category + Color)."""
    latest = process_data(df_db=df_db, df_hist=df_hist)
    if latest.empty:
        return pd.DataFrame(columns=["TEL", "Statut", "Couleur"])
    out = latest[["TEL", "Status_Category", "Color"]].copy()
    out = out.rename(columns={"Status_Category": "Statut", "Color": "Couleur"})
    return out.drop_duplicates("TEL", keep="last").reset_index(drop=True)


def merge_baseline_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Merge multiple baseline sources; first non-empty frame wins per TEL."""
    combined = pd.DataFrame(columns=["TEL", "Statut", "Couleur"])
    for frame in frames:
        if frame is None or frame.empty:
            continue
        part = frame[["TEL", "Statut", "Couleur"]].copy()
        combined = pd.concat([combined, part], ignore_index=True)
    if combined.empty:
        return combined
    return combined.drop_duplicates("TEL", keep="first").reset_index(drop=True)


def extract_ventes_from_client_exports(
    sources: list[tuple[Any, str]],
) -> pd.DataFrame:
    """Extract STATUS=1 rows from daily export_data_client files."""
    rows: list[pd.DataFrame] = []
    for source, day_label in sources:
        if hasattr(source, "seek"):
            source.seek(0)
        df = _read_excel(source, is_history=False)
        df = _normalize_columns(df)
        tel_col = _find_column(df, TEL_ALIASES) or "TEL"
        status_col = _find_column(df, STATUS_ALIASES) or "STATUS"
        df = df.rename(columns={tel_col: "TEL", status_col: "STATUS"})
        df["TEL"] = _clean_tel_db(df["TEL"])
        codes = pd.to_numeric(df["STATUS"], errors="coerce")
        ventes = df[codes == int(SALE_STATUS_CODE)].copy()
        if ventes.empty:
            lib = df.get("LIB_STATUS")
            if lib is not None:
                ventes = df[lib.astype(str).str.upper().str.strip() == "VENTE"].copy()
        ventes["Jour_Vente"] = day_label
        keep = ["TEL", "Jour_Vente"]
        for col in ("NOM", "PRENOM", "DATE", "HEURE", "LIB_STATUS"):
            upper = col if col in ventes.columns else None
            if upper:
                keep.append(upper)
        rows.append(ventes[keep])
    if not rows:
        return pd.DataFrame(
            columns=["TEL", "Jour_Vente", "NOM", "PRENOM", "DATE", "HEURE", "LIB_STATUS"]
        )
    return pd.concat(rows, ignore_index=True)


def compute_vente_origin_tracking(
    baseline: pd.DataFrame,
    ventes: pd.DataFrame,
    *,
    baseline_source: str = "baseline",
) -> dict[str, Any]:
    """Match ventes to baseline statut d'origine and compute daily rates."""
    if ventes.empty:
        empty = pd.DataFrame(
            columns=[
                "TEL",
                "Jour_Vente",
                "Statut_origine",
                "Couleur_origine",
                "Source_baseline",
                "Matched",
            ]
        )
        return {
            "detail": empty,
            "summary_by_origin": pd.DataFrame(columns=["Statut_origine", "Ventes", "Taux_%"]),
            "summary_by_day": pd.DataFrame(columns=["Jour_Vente", "Ventes", "Matchées", "Taux_match_%"]),
            "totals": {
                "vente_rows": 0,
                "vente_unique_tels": 0,
                "matched_rows": 0,
                "matched_unique_tels": 0,
                "baseline_tels": len(baseline),
            },
            "baseline_source": baseline_source,
        }

    base = baseline.copy()
    if base.empty:
        base = pd.DataFrame(columns=["TEL", "Statut", "Couleur"])
    else:
        base = base.drop_duplicates("TEL", keep="first")

    detail = ventes.copy()
    detail = detail.merge(
        base.rename(columns={"Statut": "Statut_origine", "Couleur": "Couleur_origine"}),
        on="TEL",
        how="left",
    )
    detail["Statut_origine"] = detail["Statut_origine"].fillna(NOT_FOUND_LABEL)
    detail["Couleur_origine"] = detail["Couleur_origine"].fillna("—")
    detail["Source_baseline"] = baseline_source
    detail["Matched"] = detail["Statut_origine"] != NOT_FOUND_LABEL

    matched = detail[detail["Matched"]]
    summary_by_origin = (
        matched.groupby("Statut_origine", dropna=False)
        .size()
        .reset_index(name="Ventes")
        .sort_values("Ventes", ascending=False)
    )
    total_matched = len(matched)
    if total_matched:
        summary_by_origin["Taux_%"] = (
            (100 * summary_by_origin["Ventes"] / total_matched).round(1)
        )
    else:
        summary_by_origin["Taux_%"] = 0.0

    # Conversion rate vs baseline pool per status
    if not base.empty:
        pool = (
            base.groupby("Statut")
            .size()
            .reset_index(name="Pool")
            .rename(columns={"Statut": "Statut_origine"})
        )
        conv = summary_by_origin.merge(pool, on="Statut_origine", how="left")
        conv["Pool"] = conv["Pool"].fillna(0).astype(int)
        conv["Taux_conv_pool_%"] = (
            (100 * conv["Ventes"] / conv["Pool"].replace(0, pd.NA))
            .fillna(0)
            .round(3)
        )
        summary_by_origin = conv

    summary_by_day = (
        detail.groupby("Jour_Vente", dropna=False)
        .agg(Ventes=("TEL", "count"), Matchées=("Matched", "sum"))
        .reset_index()
    )
    summary_by_day["Taux_match_%"] = (
        (100 * summary_by_day["Matchées"] / summary_by_day["Ventes"])
        .replace([float("inf"), -float("inf")], 0)
        .fillna(0)
        .round(1)
    )

    return {
        "detail": detail.reset_index(drop=True),
        "summary_by_origin": summary_by_origin,
        "summary_by_day": summary_by_day,
        "totals": {
            "vente_rows": len(detail),
            "vente_unique_tels": int(detail["TEL"].nunique()),
            "matched_rows": int(detail["Matched"].sum()),
            "matched_unique_tels": int(matched["TEL"].nunique()) if not matched.empty else 0,
            "baseline_tels": len(base),
        },
        "baseline_source": baseline_source,
        "analyzed_at": datetime.now().isoformat(timespec="seconds"),
    }


def tracking_detail_for_export(result: dict[str, Any]) -> pd.DataFrame:
    """Flatten detail frame for Excel download."""
    detail = result.get("detail", pd.DataFrame())
    if detail.empty:
        return detail
    cols = [
        c
        for c in [
            "TEL",
            "Jour_Vente",
            "PRENOM",
            "NOM",
            "Statut_origine",
            "Couleur_origine",
            "Source_baseline",
            "Matched",
            "DATE",
            "HEURE",
        ]
        if c in detail.columns
    ]
    return detail[cols].copy()
