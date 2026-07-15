"""Prévisionnel couleurs à partir d'un export Recyclage_Data_Client."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from typing import Any, BinaryIO, Literal

import pandas as pd

from engine.processor import (
    ALL_COLORS,
    TEL_ALIASES,
    SortPriority,
    _assign_color,
    _clean_tel_db,
    _find_column,
    _normalize_columns,
    apply_export_limit,
    export_excel,
)

FORECAST_OFFSET_LABELS: dict[int, str] = {
    1: "Demain (+1 jour)",
    2: "Après-demain (+2 jours)",
}

WEEK_OFFSETS: list[int] = list(range(1, 8))

FRENCH_WEEKDAYS: list[str] = [
    "Lundi",
    "Mardi",
    "Mercredi",
    "Jeudi",
    "Vendredi",
    "Samedi",
    "Dimanche",
]

COLOR_TRANSITIONS: list[tuple[str, str]] = [
    ("Red", "Orange"),
    ("Orange", "Blue"),
    ("Blue", "Green"),
]

THRESHOLD_DAYS: dict[tuple[str, str], int] = {
    ("Red", "Orange"): 15,
    ("Orange", "Blue"): 39,
    ("Blue", "Green"): 61,
}


def offset_day_label(offset: int, reference: date | None = None) -> str:
    """Libellé jour calendaire pour un offset (+1 = demain)."""
    reference = reference or date.today()
    target = reference + timedelta(days=offset)
    weekday = FRENCH_WEEKDAYS[target.weekday()]
    if offset in FORECAST_OFFSET_LABELS:
        return f"{FORECAST_OFFSET_LABELS[offset]} · {weekday}"
    return f"{weekday} (+{offset}j)"


def forecast_offset_label(offset: int, reference: date | None = None) -> str:
    return offset_day_label(offset, reference)


def _find_header_row(raw: pd.DataFrame) -> int | None:
    for index in range(min(12, len(raw))):
        cell = str(raw.iloc[index, 0]).strip().upper()
        if cell in {"INDICE", "TEL"}:
            return index
    return None


def load_recyclage_export(source: str | BinaryIO | BytesIO) -> pd.DataFrame:
    """Charge toutes les feuilles d'un export Recyclage_Data_Client."""
    if hasattr(source, "seek"):
        source.seek(0)
    workbook = pd.ExcelFile(source)
    parts: list[pd.DataFrame] = []

    for sheet in workbook.sheet_names:
        if hasattr(source, "seek"):
            source.seek(0)
        raw = pd.read_excel(source, sheet_name=sheet, header=None)
        header_idx = _find_header_row(raw)
        if header_idx is None:
            continue
        if hasattr(source, "seek"):
            source.seek(0)
        frame = pd.read_excel(source, sheet_name=sheet, header=header_idx)
        if hasattr(source, "seek"):
            source.seek(0)
        frame = _normalize_columns(frame)
        tel_col = _find_column(frame, TEL_ALIASES) or "TEL"
        if tel_col not in frame.columns:
            continue
        frame = frame.rename(columns={tel_col: "TEL"})
        frame["TEL"] = _clean_tel_db(frame["TEL"])
        frame["Status_Category"] = sheet
        if "COLOR" in frame.columns:
            frame["Color"] = frame["COLOR"]
        elif "Color" not in frame.columns:
            frame["Color"] = "Unknown"
        if "DAYS_SINCE_LAST_CALL" in frame.columns:
            frame["Days_Since_Last_Call"] = frame["DAYS_SINCE_LAST_CALL"]
        elif "Days_Since_Last_Call" not in frame.columns:
            frame["Days_Since_Last_Call"] = pd.NA
        parts.append(frame)

    if not parts:
        return pd.DataFrame()

    out = pd.concat(parts, ignore_index=True)
    out = out.drop_duplicates("TEL", keep="first")
    out["Days_Since_Last_Call"] = pd.to_numeric(
        out["Days_Since_Last_Call"], errors="coerce"
    )
    if "Color" in out.columns:
        out["Color"] = out["Color"].astype(str).str.strip()
    return out.reset_index(drop=True)


def load_exclusion_tels(source: str | BinaryIO | BytesIO) -> set[str]:
    """Charge les TEL à exclure (export recyclage, Book1, etc.)."""
    exported = load_recyclage_export(source)
    if not exported.empty and "TEL" in exported.columns:
        return set(exported["TEL"].dropna().astype(str).unique())

    if hasattr(source, "seek"):
        source.seek(0)
    workbook = pd.ExcelFile(source)
    tels: list[str] = []
    for sheet in workbook.sheet_names:
        if hasattr(source, "seek"):
            source.seek(0)
        raw = pd.read_excel(source, sheet_name=sheet, header=None)
        header_idx = _find_header_row(raw)
        if header_idx is None:
            header_idx = 0
        if hasattr(source, "seek"):
            source.seek(0)
        frame = pd.read_excel(source, sheet_name=sheet, header=header_idx)
        frame = _normalize_columns(frame)
        tel_col = _find_column(frame, TEL_ALIASES) or "TEL"
        if tel_col not in frame.columns:
            continue
        tels.extend(_clean_tel_db(frame[tel_col]).dropna().astype(str).tolist())

    return {tel for tel in tels if tel}


def apply_tel_exclusion(
    df: pd.DataFrame,
    exclude_tels: set[str] | list[str] | None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Retire les TEL présents dans le fichier d'exclusion."""
    if df.empty:
        return df.copy(), {"before": 0, "after": 0, "removed": 0, "exclusion_size": 0}

    exclusion = set(exclude_tels or [])
    before = len(df)
    if not exclusion:
        return df.copy(), {
            "before": before,
            "after": before,
            "removed": 0,
            "exclusion_size": 0,
        }

    filtered = df[~df["TEL"].astype(str).isin(exclusion)].copy().reset_index(drop=True)
    removed = before - len(filtered)
    return filtered, {
        "before": before,
        "after": len(filtered),
        "removed": removed,
        "exclusion_size": len(exclusion),
        "matched_in_source": int(df["TEL"].astype(str).isin(exclusion).sum()),
    }


def add_day_projection(df: pd.DataFrame, offset_days: int) -> pd.DataFrame:
    """Projette l'âge et la couleur après N jours."""
    if df.empty:
        return df.copy()
    out = df.copy()
    out["Days_Original"] = out["Days_Since_Last_Call"]
    out["Color_Original"] = out["Color"]
    out["Days_Projected"] = out["Days_Since_Last_Call"] + offset_days
    out["Color_Projected"] = out["Days_Projected"].apply(_assign_color)
    out["Transition"] = out.apply(
        lambda row: (
            f"{row['Color_Original']} → {row['Color_Projected']}"
            if row["Color_Original"] != row["Color_Projected"]
            else "Stable"
        ),
        axis=1,
    )
    out["Days_To_Next_Color"] = out.apply(_days_to_next_threshold, axis=1)
    return out


def _days_to_next_threshold(row: pd.Series) -> int | None:
    days = row.get("Days_Original")
    if pd.isna(days):
        return None
    days = int(days)
    color = row.get("Color_Original")
    if color == "Red":
        return max(0, 15 - days)
    if color == "Orange":
        return max(0, 39 - days)
    if color == "Blue":
        return max(0, 61 - days)
    return None


def color_pivot(
    df: pd.DataFrame,
    *,
    color_col: str = "Color",
    status_col: str = "Status_Category",
) -> pd.DataFrame:
    """Tableau statut × couleur."""
    if df.empty or color_col not in df.columns:
        return pd.DataFrame()
    pivot = (
        df.groupby([status_col, color_col])
        .size()
        .unstack(fill_value=0)
        .astype(int)
    )
    for color in ALL_COLORS:
        if color not in pivot.columns:
            pivot[color] = 0
    pivot = pivot.reindex(columns=ALL_COLORS, fill_value=0)
    pivot["Total"] = pivot.sum(axis=1)
    return pivot.sort_values("Total", ascending=False)


def global_color_counts(
    df: pd.DataFrame,
    *,
    color_col: str = "Color",
) -> dict[str, int]:
    if df.empty or color_col not in df.columns:
        return {color: 0 for color in ALL_COLORS}
    counts = df[color_col].value_counts().to_dict()
    return {color: int(counts.get(color, 0)) for color in ALL_COLORS}


def transition_summary(
    df: pd.DataFrame,
    offset_days: int,
) -> pd.DataFrame:
    """Compte les changements de couleur par statut."""
    projected = add_day_projection(df, offset_days)
    changing = projected[projected["Color_Original"] != projected["Color_Projected"]].copy()
    if changing.empty:
        return pd.DataFrame(
            columns=["Statut", "Transition", "Fiches", "Seuil (jours)"]
        )

    changing["Transition"] = (
        changing["Color_Original"] + " → " + changing["Color_Projected"]
    )
    summary = (
        changing.groupby(["Status_Category", "Transition"])
        .size()
        .reset_index(name="Fiches")
    )
    summary["Seuil (jours)"] = summary["Transition"].map(
        lambda text: THRESHOLD_DAYS.get(tuple(text.split(" → ")), "")
    )
    return summary.rename(columns={"Status_Category": "Statut"}).sort_values(
        ["Transition", "Fiches"], ascending=[True, False]
    )


def transition_totals(df: pd.DataFrame, offset_days: int) -> pd.DataFrame:
    """Totaux globaux par type de transition."""
    projected = add_day_projection(df, offset_days)
    changing = projected[projected["Color_Original"] != projected["Color_Projected"]].copy()
    if changing.empty:
        return pd.DataFrame(columns=["Transition", "Fiches", "Seuil (jours)"])

    changing["Transition"] = (
        changing["Color_Original"] + " → " + changing["Color_Projected"]
    )
    totals = changing.groupby("Transition").size().reset_index(name="Fiches")
    totals["Seuil (jours)"] = totals["Transition"].map(
        lambda text: THRESHOLD_DAYS.get(tuple(text.split(" → ")), "")
    )
    order = [f"{a} → {b}" for a, b in COLOR_TRANSITIONS]
    totals["__order"] = totals["Transition"].map(
        lambda value: order.index(value) if value in order else 99
    )
    return totals.sort_values("__order").drop(columns="__order")


def incremental_transition_totals(df: pd.DataFrame, offset_days: int) -> pd.DataFrame:
    """Transitions entre J-1 et J (nouveaux changements ce jour-là)."""
    if offset_days <= 0 or df.empty:
        return pd.DataFrame(columns=["Transition", "Fiches", "Seuil (jours)"])
    if offset_days == 1:
        return transition_totals(df, 1)

    prev = add_day_projection(df, offset_days - 1)[["TEL", "Color_Projected"]].rename(
        columns={"Color_Projected": "Color_Prev"}
    )
    curr = add_day_projection(df, offset_days)[["TEL", "Color_Projected"]].rename(
        columns={"Color_Projected": "Color_Curr"}
    )
    merged = prev.merge(curr, on="TEL", how="inner")
    changing = merged[merged["Color_Prev"] != merged["Color_Curr"]].copy()
    if changing.empty:
        return pd.DataFrame(columns=["Transition", "Fiches", "Seuil (jours)"])

    changing["Transition"] = changing["Color_Prev"] + " → " + changing["Color_Curr"]
    totals = changing.groupby("Transition").size().reset_index(name="Fiches")
    totals["Seuil (jours)"] = totals["Transition"].map(
        lambda text: THRESHOLD_DAYS.get(tuple(text.split(" → ")), "")
    )
    order = [f"{a} → {b}" for a, b in COLOR_TRANSITIONS]
    totals["__order"] = totals["Transition"].map(
        lambda value: order.index(value) if value in order else 99
    )
    return totals.sort_values("__order").drop(columns="__order")


def week_timeline(
    df: pd.DataFrame,
    *,
    offsets: list[int] | None = None,
    reference: date | None = None,
) -> pd.DataFrame:
    """Évolution des couleurs sur la semaine (+1 à +7)."""
    reference = reference or date.today()
    offsets = offsets or WEEK_OFFSETS
    if df.empty:
        return pd.DataFrame()

    today_counts = global_color_counts(df, color_col="Color")
    rows: list[dict[str, Any]] = []

    for offset in offsets:
        projected = add_day_projection(df, offset)
        global_counts = global_color_counts(projected, color_col="Color_Projected")
        target_date = reference + timedelta(days=offset)
        incremental = incremental_transition_totals(df, offset)
        inc_parts = [
            f"{row.Transition}: {int(row.Fiches)}"
            for row in incremental.itertuples()
        ]
        rows.append(
            {
                "Offset": offset,
                "Jour": FRENCH_WEEKDAYS[target_date.weekday()],
                "Date": target_date.strftime("%d/%m/%Y"),
                "Red": global_counts.get("Red", 0),
                "Orange": global_counts.get("Orange", 0),
                "Blue": global_counts.get("Blue", 0),
                "Green": global_counts.get("Green", 0),
                "Δ Orange vs auj.": global_counts.get("Orange", 0) - today_counts.get("Orange", 0),
                "Changements cumulés": int(
                    (projected["Color_Original"] != projected["Color_Projected"]).sum()
                ),
                "Nouveaux changements": int(incremental["Fiches"].sum()) if not incremental.empty else 0,
                "Transitions du jour": " · ".join(inc_parts) if inc_parts else "—",
            }
        )

    return pd.DataFrame(rows)


def red_days_breakdown(
    df: pd.DataFrame,
    offset_days: int = 0,
    *,
    by_status: bool = False,
) -> pd.DataFrame:
    """Détail des rouges par jours depuis dernier contact (14, 13, 12…)."""
    if df.empty:
        return pd.DataFrame()

    if offset_days == 0:
        work = df[df["Color"] == "Red"].copy()
        days_col = "Days_Since_Last_Call"
        if work.empty:
            return pd.DataFrame()
        work["Days_Bucket"] = pd.to_numeric(work[days_col], errors="coerce").astype("Int64")
        work["Days_Projected"] = work["Days_Bucket"]
        work["Color_Projected"] = "Red"
    else:
        projected = add_day_projection(df, offset_days)
        work = projected[projected["Color_Original"] == "Red"].copy()
        if work.empty:
            return pd.DataFrame()
        work["Days_Bucket"] = pd.to_numeric(work["Days_Original"], errors="coerce").astype("Int64")
        work["Days_Projected"] = pd.to_numeric(work["Days_Projected"], errors="coerce").astype("Int64")
        work["Color_Projected"] = work["Color_Projected"]

    work = work.dropna(subset=["Days_Bucket"])
    work["Days_Bucket"] = work["Days_Bucket"].astype(int)
    work = work[work["Days_Bucket"] < 15]
    if work.empty:
        return pd.DataFrame()

    work["Jours avant Orange"] = 15 - work["Days_Bucket"]
    work["Passe Orange à J+"] = work["Jours avant Orange"].apply(
        lambda days: "Déjà orange" if days <= offset_days else f"J+{int(days)}"
    )

    group_cols = ["Status_Category", "Days_Bucket"] if by_status else ["Days_Bucket"]
    detail = (
        work.groupby(group_cols, dropna=False)
        .agg(
            Fiches=("TEL", "count"),
            Jours_projetés=("Days_Projected", "min"),
            Couleur_projetée=("Color_Projected", lambda s: s.mode().iloc[0] if not s.empty else "Red"),
            Jours_avant_Orange=("Jours avant Orange", "min"),
            Passe_Orange=("Passe Orange à J+", "first"),
        )
        .reset_index()
    )
    if by_status:
        detail = detail.rename(columns={"Status_Category": "Statut", "Days_Bucket": "Jours contact"})
    else:
        detail = detail.rename(columns={"Days_Bucket": "Jours contact"})
    detail = detail.sort_values(
        ["Jours contact"] if not by_status else ["Statut", "Jours contact"],
        ascending=[False] if not by_status else [True, False],
    )
    return detail.reset_index(drop=True)


def red_days_week_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Matrice rouges : chaque ligne = jours contact (14→0), colonnes = effectif restant rouge."""
    if df.empty:
        return pd.DataFrame()

    today_reds = df[df["Color"] == "Red"].copy()
    today_reds["Days_Bucket"] = pd.to_numeric(
        today_reds["Days_Since_Last_Call"], errors="coerce"
    ).astype("Int64")
    today_reds = today_reds.dropna(subset=["Days_Bucket"])
    today_reds["Days_Bucket"] = today_reds["Days_Bucket"].astype(int)
    today_reds = today_reds[today_reds["Days_Bucket"] < 15]

    projections = {offset: add_day_projection(df, offset) for offset in WEEK_OFFSETS}
    rows: list[dict[str, Any]] = []

    for bucket in range(14, -1, -1):
        days_until_orange = 15 - bucket
        row: dict[str, Any] = {
            "Jours contact": bucket,
            "Jours avant Orange": days_until_orange,
            "Passe Orange à": f"J+{days_until_orange}" if days_until_orange > 0 else "—",
            "Aujourd'hui": int((today_reds["Days_Bucket"] == bucket).sum()),
        }
        for offset in WEEK_OFFSETS:
            projected = projections[offset]
            mask = (
                (projected["Color_Original"] == "Red")
                & (pd.to_numeric(projected["Days_Original"], errors="coerce").astype(int) == bucket)
                & (projected["Color_Projected"] == "Red")
            )
            row[f"J+{offset}"] = int(mask.sum())
        rows.append(row)

    return pd.DataFrame(rows)


def aging_detail(
    df: pd.DataFrame,
    offset_days: int,
    *,
    color_filter: str | None = None,
) -> pd.DataFrame:
    """Détail jour actuel → jour projeté (ex. rouge à 10j → 11j demain)."""
    projected = add_day_projection(df, offset_days)
    if color_filter:
        projected = projected[projected["Color_Original"] == color_filter]
    if projected.empty:
        return pd.DataFrame(
            columns=[
                "Statut",
                "Jours actuels",
                "Jours projetés",
                "Couleur actuelle",
                "Couleur projetée",
                "Fiches",
            ]
        )

    detail = (
        projected.groupby(
            [
                "Status_Category",
                "Days_Original",
                "Days_Projected",
                "Color_Original",
                "Color_Projected",
            ]
        )
        .size()
        .reset_index(name="Fiches")
    )
    detail = detail.rename(
        columns={
            "Status_Category": "Statut",
            "Days_Original": "Jours actuels",
            "Days_Projected": "Jours projetés",
            "Color_Original": "Couleur actuelle",
            "Color_Projected": "Couleur projetée",
        }
    )
    return detail.sort_values(
        ["Statut", "Jours actuels", "Jours projetés"], ascending=[True, True, True]
    )


def forecast_snapshot(
    df: pd.DataFrame,
    offsets: list[int] | None = None,
    *,
    reference: date | None = None,
) -> dict[str, Any]:
    """Résumé complet aujourd'hui + offsets demandés."""
    reference = reference or date.today()
    offsets = offsets or WEEK_OFFSETS
    result: dict[str, Any] = {
        "total_rows": len(df),
        "reference_date": reference.isoformat(),
        "today": {
            "global": global_color_counts(df, color_col="Color"),
            "by_status": color_pivot(df, color_col="Color"),
        },
        "week_timeline": week_timeline(df, offsets=offsets, reference=reference),
        "red_days_today": red_days_breakdown(df, 0),
        "red_days_by_status_today": red_days_breakdown(df, 0, by_status=True),
        "red_days_week_matrix": red_days_week_matrix(df),
        "offsets": {},
    }
    for offset in offsets:
        projected = add_day_projection(df, offset)
        target_date = reference + timedelta(days=offset)
        result["offsets"][offset] = {
            "label": forecast_offset_label(offset, reference),
            "weekday": FRENCH_WEEKDAYS[target_date.weekday()],
            "date": target_date.strftime("%d/%m/%Y"),
            "global": global_color_counts(projected, color_col="Color_Projected"),
            "by_status": color_pivot(projected, color_col="Color_Projected"),
            "red_days": red_days_breakdown(df, offset),
            "red_days_by_status": red_days_breakdown(df, offset, by_status=True),
            "transitions_total": transition_totals(df, offset),
            "transitions_incremental": incremental_transition_totals(df, offset),
            "transitions_by_status": transition_summary(df, offset),
            "stable_count": int(
                (projected["Color_Original"] == projected["Color_Projected"]).sum()
            ),
            "changing_count": int(
                (projected["Color_Original"] != projected["Color_Projected"]).sum()
            ),
        }
    return result


def prepare_forecast_export(
    df: pd.DataFrame,
    offset_days: int,
    *,
    status_color_quotas: dict[str, dict[str, int]],
    sort_priority: SortPriority = "oldest",
) -> pd.DataFrame:
    """Sélectionne des lignes selon les quotas sur la couleur projetée."""
    projected = add_day_projection(df, offset_days)
    export_df = projected.copy()
    export_df["Color"] = export_df["Color_Projected"]
    export_df["Days_Since_Last_Call"] = export_df["Days_Projected"]
    export_df["Forecast_Offset_Days"] = offset_days
    return apply_export_limit(
        export_df,
        limit_scope="custom",
        status_color_quotas=status_color_quotas,
        sort_priority=sort_priority,
    )


def export_forecast_selection(
    df: pd.DataFrame,
    offset_days: int,
    *,
    status_color_quotas: dict[str, dict[str, int]],
    sort_priority: SortPriority = "oldest",
) -> tuple[bytes, pd.DataFrame, dict[str, Any]]:
    """Génère l'Excel final avec masque couleur sur la projection."""
    limited = prepare_forecast_export(
        df,
        offset_days,
        status_color_quotas=status_color_quotas,
        sort_priority=sort_priority,
    )
    if limited.empty:
        raise ValueError("Aucune ligne sélectionnée avec ces quotas.")

    selected_statuses = sorted(limited["Status_Category"].dropna().unique())
    selected_colors = sorted(limited["Color"].dropna().unique())
    excel_bytes = export_excel(
        limited,
        selected_statuses=selected_statuses,
        selected_colors=selected_colors,
        max_rows=None,
        sort_priority=sort_priority,
    )

    summary = {
        "total_selected": len(limited),
        "offset_days": offset_days,
        "offset_label": forecast_offset_label(offset_days),
        "by_status": limited["Status_Category"].value_counts().to_dict(),
        "by_color": limited["Color"].value_counts().to_dict(),
        "by_status_color": (
            limited.groupby(["Status_Category", "Color"])
            .size()
            .reset_index(name="Lignes")
            .to_dict(orient="records")
        ),
        "transitions_in_selection": (
            limited[limited["Color_Original"] != limited["Color"]]
            .groupby(
                limited["Color_Original"].astype(str)
                + " → "
                + limited["Color"].astype(str)
            )
            .size()
            .to_dict()
        ),
    }
    return excel_bytes, limited, summary


def available_projected_counts(
    df: pd.DataFrame,
    offset_days: int,
) -> dict[str, dict[str, int]]:
    """Quotas max disponibles par statut × couleur projetée."""
    projected = add_day_projection(df, offset_days)
    counts: dict[str, dict[str, int]] = {}
    for status in sorted(projected["Status_Category"].dropna().unique()):
        counts[status] = {color: 0 for color in ALL_COLORS}
        status_rows = projected[projected["Status_Category"] == status]
        for color, total in status_rows["Color_Projected"].value_counts().items():
            if color in counts[status]:
                counts[status][color] = int(total)
    return counts
