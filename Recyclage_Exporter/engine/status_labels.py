"""Resolve human-readable status labels beyond DEFAULT_STATUS_MAPPING."""

from __future__ import annotations

from typing import Any

import pandas as pd

from engine.processor import DEFAULT_STATUS_MAPPING, _map_status

_JUNK_LABELS = {"", "nan", "none", "null", "0", "1", "2", "3", "4", "5", "6", "7", "-1"}


def is_meaningful_label(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    text = str(value).strip()
    if not text or text.casefold() in _JUNK_LABELS:
        return False
    if text.lstrip("-").isdigit():
        return False
    return True


def _status_code_text(status: pd.Series) -> pd.Series:
    codes = pd.to_numeric(status, errors="coerce")
    out = pd.Series(index=status.index, dtype=str)
    valid = codes.notna()
    out.loc[valid] = codes.loc[valid].astype(int).astype(str)
    out.loc[~valid] = status.loc[~valid].astype(str).str.strip()
    return out.replace({"": pd.NA, "nan": pd.NA})


def apply_resolved_status_labels(
    frame: pd.DataFrame,
    *,
    status_col: str = "STATUS",
    status_mapping: dict[int, str] | None = None,
    target_col: str = "Status_Label",
) -> pd.Series:
    """Vectorized resolved labels for a history/client frame."""
    status_mapping = status_mapping or DEFAULT_STATUS_MAPPING
    mapped = _map_status(frame[status_col], status_mapping)
    label = mapped.copy()

    for col in ("LIB_STATUS", "LIB_DETAIL"):
        if col not in frame.columns:
            continue
        raw = frame[col]
        meaningful = raw.where(raw.apply(is_meaningful_label))
        label = label.fillna(meaningful)

    if "STATUS_STATUS" in frame.columns:
        sub_mapped = _map_status(frame["STATUS_STATUS"], status_mapping)
        code_text = _status_code_text(frame[status_col])
        fallback = sub_mapped.astype(str) + " (sous-code " + frame["STATUS_STATUS"].astype(str) + " · statut " + code_text.astype(str) + ")"
        fallback = fallback.where(sub_mapped.notna())
        label = label.fillna(fallback)

    code_text = _status_code_text(frame[status_col])
    label = label.fillna("Code " + code_text.astype(str))
    return label.fillna("Autre").rename(target_col)


def resolve_status_label(
    status: object,
    *,
    lib_status: object = None,
    lib_detail: object = None,
    status_status: object = None,
    status_mapping: dict[int, str] | None = None,
) -> str:
    row = pd.DataFrame(
        {
            "STATUS": [status],
            "LIB_STATUS": [lib_status],
            "LIB_DETAIL": [lib_detail],
            "STATUS_STATUS": [status_status],
        }
    )
    return str(apply_resolved_status_labels(row, status_mapping=status_mapping).iloc[0])


def build_status_code_catalog(
    frame: pd.DataFrame,
    *,
    status_mapping: dict[int, str] | None = None,
) -> pd.DataFrame:
    """Catalogue de tous les codes STATUS avec leurs libellés observés."""
    status_mapping = status_mapping or DEFAULT_STATUS_MAPPING
    if frame.empty or "STATUS" not in frame.columns:
        return pd.DataFrame(
            columns=[
                "Code_STATUS",
                "Libellé_résolu",
                "Dans_mapping",
                "LIB_DETAIL_principal",
                "Occurrences",
            ]
        )

    work = frame.copy()
    work["Code_STATUS"] = _status_code_text(work["STATUS"])
    work["Status_Label"] = apply_resolved_status_labels(work, status_mapping=status_mapping)
    if "LIB_DETAIL" in work.columns:
        work["_detail"] = work["LIB_DETAIL"].where(work["LIB_DETAIL"].apply(is_meaningful_label))
    else:
        work["_detail"] = pd.NA

    rows: list[dict[str, Any]] = []
    for code, group in work.groupby("Code_STATUS", dropna=False):
        if not code or pd.isna(code):
            continue
        try:
            in_map = int(code) in status_mapping
        except ValueError:
            in_map = False
        top_detail = ""
        if group["_detail"].notna().any():
            top_detail = str(group["_detail"].value_counts().index[0])
        top_label = str(group["Status_Label"].value_counts().index[0])
        rows.append(
            {
                "Code_STATUS": code,
                "Libellé_résolu": top_label,
                "Dans_mapping": "Oui" if in_map else "Non",
                "LIB_DETAIL_principal": top_detail,
                "Occurrences": len(group),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("Occurrences", ascending=False)
    return out.reset_index(drop=True)


def breakdown_autre_ventes(vente_transitions: pd.DataFrame) -> pd.DataFrame:
    """Détail des ventes classées Autre : codes et vrais noms."""
    empty = pd.DataFrame(
        columns=[
            "Code_STATUS",
            "Libellé_avant_vente",
            "LIB_DETAIL",
            "Sous_statut_STATUS_STATUS",
            "Ventes",
            "Part_%",
        ]
    )
    if vente_transitions.empty:
        return empty

    autre = vente_transitions[vente_transitions["Prior_Status"] == "Autre"].copy()
    if autre.empty:
        return empty

    autre["Code_STATUS"] = autre.get("Prior_Status_Code", pd.Series(dtype=str)).astype(str)
    autre["Libellé_avant_vente"] = autre.get(
        "Prior_Status_Label", autre["Code_STATUS"].apply(lambda c: f"Code {c}")
    )

    group_cols = ["Code_STATUS", "Libellé_avant_vente"]
    if "Prior_LIB_DETAIL" in autre.columns:
        autre["LIB_DETAIL"] = autre["Prior_LIB_DETAIL"].where(
            autre["Prior_LIB_DETAIL"].apply(is_meaningful_label)
        )
        group_cols.append("LIB_DETAIL")
    else:
        autre["LIB_DETAIL"] = pd.NA

    if "Prior_STATUS_STATUS" in autre.columns:
        autre["Sous_statut_STATUS_STATUS"] = autre["Prior_STATUS_STATUS"].apply(
            lambda v: resolve_status_label(v) if pd.notna(v) else pd.NA
        )
        group_cols.append("Sous_statut_STATUS_STATUS")
    else:
        autre["Sous_statut_STATUS_STATUS"] = pd.NA

    grouped = (
        autre.groupby(group_cols, dropna=False)
        .size()
        .reset_index(name="Ventes")
        .sort_values("Ventes", ascending=False)
    )
    total = int(grouped["Ventes"].sum())
    grouped["Part_%"] = (100 * grouped["Ventes"] / total).round(2) if total else 0.0
    return grouped.reset_index(drop=True)
