"""Persistent client DB, history, and Onoff store with daily updates."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd

from engine import storage
from engine.processor import (
    TEL_ALIASES,
    _clean_tel_db,
    _clean_tel_hist_initial,
    _find_column,
    _normalize_columns,
    _read_csv,
    _read_excel,
    _is_csv_source,
    last_onoff_call_durations,
    merge_onoff_calls,
    attach_repondeur_profiles,
    read_onoff_calls,
)

STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "store"


def _ensure_storage() -> None:
    """Initialize storage and reload module so Streamlit picks up engine changes."""
    import importlib

    importlib.reload(storage)
    storage.init_schema()
    storage.migrate_pickle_store_if_needed()


def _load_onoff_totals() -> pd.DataFrame:
    _ensure_storage()
    if hasattr(storage, "load_onoff_totals"):
        return storage.load_onoff_totals()
    return pd.DataFrame(columns=["TEL", "Total_Duration_Seconds", "Total_Duration", "Call_Count"])


def _replace_onoff_totals(df: pd.DataFrame) -> None:
    _ensure_storage()
    if hasattr(storage, "replace_onoff_totals"):
        storage.replace_onoff_totals(df)
        return
    raise RuntimeError(
        "Fonction replace_onoff_totals indisponible. Redémarrez Streamlit (Ctrl+C puis ./run.sh)."
    )


def store_exists() -> bool:
    _ensure_storage()
    return storage.store_has_data()


def _load_meta() -> dict[str, Any]:
    _ensure_storage()
    return storage.load_meta()


def _save_meta(meta: dict[str, Any]) -> None:
    storage.save_meta(meta)


def _prepare_db_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = _normalize_columns(df.copy())
    tel_col = _find_column(out, TEL_ALIASES)
    if not tel_col:
        raise ValueError("Colonne TEL introuvable dans la base client.")
    out = out.rename(columns={tel_col: "TEL"})
    out["TEL"] = _clean_tel_db(out["TEL"])
    out = out[out["TEL"].notna() & (out["TEL"].astype(str).str.lower() != "nan")]
    out["TEL"] = out["TEL"].astype(str).str.strip()
    return out.drop_duplicates(subset=["TEL"], keep="last").reset_index(drop=True)


def _prepare_hist_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = _normalize_columns(df.copy())
    tel_col = _find_column(out, TEL_ALIASES)
    if not tel_col:
        raise ValueError("Colonne TEL introuvable dans l'historique.")
    out = out.rename(columns={tel_col: "TEL"})
    out["TEL_cleaned_initial"] = _clean_tel_hist_initial(out["TEL"])
    out["TEL"] = out["TEL_cleaned_initial"]
    out = out[out["TEL"].notna() & (out["TEL"].astype(str).str.lower() != "nan")]
    return out.reset_index(drop=True)


def _read_import(source: str | Path | BinaryIO, *, is_history: bool) -> pd.DataFrame:
    if _is_csv_source(source):
        if not is_history:
            raise ValueError("Seul l'historique accepte les CSV pour le moment.")
        return _read_csv(source)
    return _read_excel(source, is_history=is_history)


def load_db() -> pd.DataFrame:
    _ensure_storage()
    df = storage.load_client_db()
    if df.empty:
        raise FileNotFoundError("Base client non initialisée.")
    if "TEL" in df.columns:
        df = df.copy()
        df["TEL"] = _clean_tel_db(df["TEL"])
    return df


def load_history() -> pd.DataFrame:
    _ensure_storage()
    df = storage.load_history()
    if df.empty:
        raise FileNotFoundError("Historique non initialisé.")
    return df


def load_onoff_calls() -> pd.DataFrame:
    _ensure_storage()
    return storage.load_onoff_calls()


def save_db(df: pd.DataFrame) -> None:
    _ensure_storage()
    storage.replace_client_db(df)


def save_history(df: pd.DataFrame) -> None:
    _ensure_storage()
    storage.replace_history(df)


def save_onoff_calls(df: pd.DataFrame) -> None:
    _ensure_storage()
    storage.replace_onoff_calls(df)


def _count_onoff_totals() -> int:
    """Count Onoff totals rows (compatible with older cached storage modules)."""
    if hasattr(storage, "count_onoff_totals"):
        return storage.count_onoff_totals()
    if hasattr(storage, "load_onoff_totals"):
        return len(storage.load_onoff_totals())
    return 0


def get_store_stats() -> dict[str, Any]:
    _ensure_storage()
    meta = _load_meta()
    initialized = store_exists()
    stats: dict[str, Any] = {
        "initialized": initialized,
        "backend": storage.backend_label(),
        "database_url_hint": _database_url_hint(),
        "last_update": meta.get("last_update"),
        "db_rows": storage.count_client_rows(),
        "hist_rows": storage.count_history_rows(),
        "onoff_rows": storage.count_onoff_rows(),
        "onoff_totals_rows": _count_onoff_totals(),
        "updates": meta.get("updates", []),
    }
    if initialized:
        stats["db_tels"] = storage.count_client_tels()
        hist = load_history()
        stats["hist_tels"] = int(_prepare_hist_frame(hist)["TEL"].nunique())
        onoff = load_onoff_calls()
        stats["onoff_tels"] = int(onoff["TEL"].nunique()) if not onoff.empty else 0
    return stats


def _database_url_hint() -> str:
    import os

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return f"SQLite local ({storage.STORE_DIR / 'recyclage.db'})"
    if url.startswith("postgresql"):
        return "PostgreSQL (DATABASE_URL)"
    return "Base SQL configurée (DATABASE_URL)"


def _save_merged_onoff(
    sources: list[str | Path | BinaryIO] | None = None,
    *,
    append: bool = False,
) -> dict[str, Any]:
    """Merge Onoff exports (including totals sheets) and persist calls + per-TEL totals."""
    existing_calls = load_onoff_calls() if append else pd.DataFrame()
    existing_totals = _load_onoff_totals() if append else pd.DataFrame()

    all_calls, totals, merge_stats = merge_onoff_calls(
        sources or [],
        existing_calls=existing_calls if append and not existing_calls.empty else None,
        existing_totals=existing_totals if append and not existing_totals.empty else None,
    )

    save_onoff_calls(all_calls)
    _replace_onoff_totals(totals)
    return {
        "onoff_rows": len(all_calls),
        "onoff_totals_rows": len(totals),
        "onoff_unique_tels": int(totals["TEL"].nunique()) if not totals.empty else 0,
        "onoff_total_duration_seconds": int(totals["Total_Duration_Seconds"].sum())
        if not totals.empty
        else 0,
        **merge_stats,
    }


def initialize_store(
    db_source: str | Path | BinaryIO,
    hist_source: str | Path | BinaryIO,
    onoff_sources: list[str | Path | BinaryIO] | None = None,
    *,
    label: str = "initialisation",
) -> dict[str, Any]:
    """Create the persistent store from master files."""
    _ensure_storage()
    df_db = _prepare_db_frame(_read_import(db_source, is_history=False))
    df_hist = _prepare_hist_frame(_read_import(hist_source, is_history=True))

    save_db(df_db)
    save_history(df_hist)

    onoff_stats: dict[str, Any] = {"onoff_rows": 0, "onoff_totals_rows": 0}
    if onoff_sources:
        onoff_stats = _save_merged_onoff(onoff_sources, append=False)
    else:
        save_onoff_calls(pd.DataFrame(columns=["TEL", "Duration_Seconds"]))
        _replace_onoff_totals(pd.DataFrame())

    stats = {
        "db_rows": len(df_db),
        "hist_rows": len(df_hist),
        "onoff_rows": onoff_stats.get("onoff_rows", 0),
        "onoff_totals_rows": onoff_stats.get("onoff_totals_rows", 0),
        "onoff_unique_tels": onoff_stats.get("onoff_unique_tels", 0),
        "db_tels": int(df_db["TEL"].nunique()),
        "hist_tels": int(df_hist["TEL"].nunique()),
    }
    meta = _load_meta()
    meta["last_update"] = datetime.now().isoformat(timespec="seconds")
    meta.setdefault("updates", []).append({"type": label, "at": meta["last_update"], **stats})
    _save_meta(meta)
    return stats


def _merge_client_db(
    master: pd.DataFrame,
    daily: pd.DataFrame,
    *,
    allow_new_tels: bool = False,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Merge daily DB rows into master by TEL (update STATUS and all columns)."""
    master = master.drop_duplicates(subset=["TEL"], keep="last").copy()
    daily = daily.drop_duplicates(subset=["TEL"], keep="last").copy()

    master_tels = set(master["TEL"].dropna().astype(str))
    daily_tels = set(daily["TEL"].dropna().astype(str))
    common = master_tels.intersection(daily_tels)
    unmatched = daily_tels - master_tels

    merged = master.copy()
    daily_map = daily.set_index("TEL")

    for tel in common:
        mask = merged["TEL"] == tel
        for col in daily.columns:
            if col == "TEL":
                continue
            value = daily_map.at[tel, col]
            if col not in merged.columns:
                merged[col] = pd.NA
            merged.loc[mask, col] = value

    added = 0
    if allow_new_tels and unmatched:
        new_rows = daily[daily["TEL"].isin(unmatched)].copy()
        merged = pd.concat([merged, new_rows], ignore_index=True)
        added = len(new_rows)

    merged = merged.drop_duplicates(subset=["TEL"], keep="last").reset_index(drop=True)
    return merged, {
        "updated_tels": len(common),
        "added_tels": added,
        "skipped_new_tels": len(unmatched) if not allow_new_tels else 0,
        "daily_tels": len(daily_tels),
        "master_tels_before": len(master_tels),
        "total_db_rows": len(merged),
    }


def update_db_from_daily(
    daily_source: str | Path | BinaryIO,
    *,
    allow_new_tels: bool = False,
) -> dict[str, int]:
    """Update master DB statuses/fields for matching TELs."""
    return update_db_from_daily_files([daily_source], allow_new_tels=allow_new_tels)


def update_db_from_daily_files(
    daily_sources: list[str | Path | BinaryIO],
    *,
    allow_new_tels: bool = False,
) -> dict[str, int]:
    """Merge one or more daily DB exports into the master by TEL."""
    if not daily_sources:
        raise ValueError("Aucun fichier data du jour.")

    master = _prepare_db_frame(load_db())
    master_tels_before = int(master["TEL"].nunique())
    totals = {
        "updated_tels": 0,
        "added_tels": 0,
        "skipped_new_tels": 0,
        "daily_tels": 0,
        "files_processed": 0,
        "master_tels_before": master_tels_before,
    }

    for source in daily_sources:
        daily = _prepare_db_frame(_read_import(source, is_history=False))
        master, stats = _merge_client_db(master, daily, allow_new_tels=allow_new_tels)
        totals["updated_tels"] += stats["updated_tels"]
        totals["added_tels"] += stats.get("added_tels", 0)
        totals["skipped_new_tels"] += stats.get("skipped_new_tels", 0)
        totals["daily_tels"] += stats.get("daily_tels", 0)
        totals["files_processed"] += 1

    save_db(master)
    totals["total_db_rows"] = len(master)
    return totals


def append_history_from_daily(daily_source: str | Path | BinaryIO) -> dict[str, int]:
    """Append new history rows from the daily export."""
    return append_history_from_daily_files([daily_source])


def append_history_from_daily_files(
    daily_sources: list[str | Path | BinaryIO],
) -> dict[str, int]:
    """Append history rows from one or more daily exports."""
    if not daily_sources:
        raise ValueError("Aucun fichier histo du jour.")

    rows_added = 0
    for source in daily_sources:
        daily = _prepare_hist_frame(_read_import(source, is_history=True))
        rows_added += storage.append_history(daily)

    return {
        "rows_added": rows_added,
        "total_hist_rows": storage.count_history_rows(),
        "files_processed": len(daily_sources),
    }


def append_onoff_from_daily(daily_sources: list[str | Path | BinaryIO]) -> dict[str, int]:
    """Append Onoff call rows from daily export(s), merging totals sheets too."""
    if not daily_sources:
        return {
            "rows_added": 0,
            "total_onoff_rows": storage.count_onoff_rows(),
            "total_onoff_totals": _count_onoff_totals(),
        }

    before_calls = storage.count_onoff_rows()
    before_totals = _count_onoff_totals()
    merge_stats = _save_merged_onoff(daily_sources, append=True)
    onoff = load_onoff_calls()
    return {
        "rows_added": storage.count_onoff_rows() - before_calls,
        "totals_rows": _count_onoff_totals(),
        "totals_added": _count_onoff_totals() - before_totals,
        "total_onoff_rows": len(onoff),
        "unique_tels": int(merge_stats.get("onoff_unique_tels", 0)),
        "total_duration_seconds": int(merge_stats.get("onoff_total_duration_seconds", 0)),
    }


def import_onoff_sources(
    sources: list[str | Path | BinaryIO],
    *,
    append: bool = False,
    label: str = "import onoff",
) -> dict[str, Any]:
    """Import and merge Onoff files (call logs + totals sheets) into the store."""
    if not sources:
        raise ValueError("Fournissez au moins un fichier Onoff.")
    stats = _save_merged_onoff(sources, append=append)
    meta = _load_meta()
    meta["last_update"] = datetime.now().isoformat(timespec="seconds")
    meta.setdefault("updates", []).append({"type": label, "at": meta["last_update"], **stats})
    _save_meta(meta)
    stats["store"] = get_store_stats()
    return stats


def _normalize_upload_list(
    value: str | Path | BinaryIO | list[str | Path | BinaryIO] | None,
) -> list[str | Path | BinaryIO]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def apply_daily_update(
    *,
    daily_db: str | Path | BinaryIO | list[str | Path | BinaryIO] | None = None,
    daily_hist: str | Path | BinaryIO | list[str | Path | BinaryIO] | None = None,
    daily_onoff: list[str | Path | BinaryIO] | None = None,
    allow_new_tels: bool = False,
    label: str | None = None,
) -> dict[str, Any]:
    """Apply a daily import: update DB, append history and Onoff."""
    if not store_exists():
        raise FileNotFoundError(
            "Base non initialisée. Importez d'abord la DB et l'historique master."
        )

    daily_db_files = _normalize_upload_list(daily_db)
    daily_hist_files = _normalize_upload_list(daily_hist)
    if not daily_db_files and not daily_hist_files and not daily_onoff:
        raise ValueError("Fournissez au moins un fichier du jour (DB, historique ou Onoff).")

    report: dict[str, Any] = {}
    if daily_db_files:
        report["vente_baseline_snapshot"] = capture_vente_baseline_from_store()
        report["db"] = update_db_from_daily_files(
            daily_db_files,
            allow_new_tels=allow_new_tels,
        )
    if daily_hist_files:
        report["history"] = append_history_from_daily_files(daily_hist_files)
    if daily_onoff:
        report["onoff"] = append_onoff_from_daily(daily_onoff)

    meta = _load_meta()
    meta["last_update"] = datetime.now().isoformat(timespec="seconds")
    meta.setdefault("updates", []).append(
        {
            "type": label or "mise à jour quotidienne",
            "at": meta["last_update"],
            **report,
        }
    )
    _save_meta(meta)
    report["store"] = get_store_stats()
    return report


def get_fichier_values() -> list[str]:
    """Return sorted unique FICHIER values from the client DB."""
    _ensure_storage()
    if not store_exists():
        return []
    df = load_db()
    return _fichier_values_from_frame(df)


def get_fichier_values_from_db_source(
    db_source: str | Path | BinaryIO,
) -> list[str]:
    """Read FICHIER values from an uploaded DB file without persisting."""
    df = _prepare_db_frame(_read_import(db_source, is_history=False))
    return _fichier_values_from_frame(df)


def _fichier_values_from_frame(df: pd.DataFrame) -> list[str]:
    if "FICHIER" not in df.columns:
        return []
    values = (
        df["FICHIER"]
        .dropna()
        .astype(str)
        .str.strip()
    )
    values = values[(values != "") & (values.str.lower() != "nan")]
    return sorted(values.unique().tolist())


def sync_fichier_from_db(df: pd.DataFrame) -> pd.DataFrame:
    """Attach the canonical FICHIER column from the client DB (one value per TEL)."""
    if df.empty or "TEL" not in df.columns:
        return df
    try:
        db = load_db()
    except FileNotFoundError:
        return df
    if "FICHIER" not in db.columns:
        return df

    db_fichier = (
        db[["TEL", "FICHIER"]]
        .dropna(subset=["TEL"])
        .drop_duplicates(subset=["TEL"], keep="last")
        .copy()
    )
    db_fichier["TEL"] = db_fichier["TEL"].astype(str).str.strip()
    db_fichier["FICHIER"] = db_fichier["FICHIER"].fillna("").astype(str).str.strip()

    out = df.copy()
    out["TEL"] = out["TEL"].astype(str).str.strip()
    out = out.drop(columns=[c for c in out.columns if c == "FICHIER"], errors="ignore")
    return out.merge(db_fichier, on="TEL", how="left")


def apply_fichier_filter(
    df: pd.DataFrame,
    fichiers: list[str] | None,
    *,
    mode: str = "include",
) -> pd.DataFrame:
    """Filter export rows by FICHIER (include = keep only selected, exclude = drop selected)."""
    if df.empty or not fichiers:
        return df

    out = sync_fichier_from_db(df)
    if "FICHIER" not in out.columns:
        return out

    selected = {str(value).strip() for value in fichiers if str(value).strip()}
    if not selected:
        return out

    normalized = out["FICHIER"].fillna("").astype(str).str.strip()
    if mode == "exclude":
        mask = ~normalized.isin(selected)
    else:
        mask = normalized.isin(selected)
    return out[mask].copy()


def _history_duration_totals(hist_df: pd.DataFrame) -> pd.DataFrame:
    """Sum history DUREE (seconds) per TEL — fallback only when Onoff is absent."""
    from engine.processor import _clean_tel_db, _format_duration

    if hist_df.empty or "DUREE" not in hist_df.columns:
        return pd.DataFrame(columns=["TEL", "History_Duration_Seconds"])

    hist = hist_df.copy()
    hist["TEL"] = _clean_tel_db(hist["TEL"])
    hist["DUREE_SEC"] = pd.to_numeric(hist["DUREE"], errors="coerce").fillna(0).astype(int)
    totals = (
        hist.groupby("TEL", as_index=False)["DUREE_SEC"]
        .sum()
        .rename(columns={"DUREE_SEC": "History_Duration_Seconds"})
    )
    totals["History_Duration"] = totals["History_Duration_Seconds"].map(_format_duration)
    return totals


def attach_store_onoff(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Attach total Onoff call duration per TEL from the persisted Onoff store."""
    from engine.processor import _clean_tel_db, _format_duration

    db_tels = set(df["TEL"].dropna().astype(str).unique())
    totals = _load_onoff_totals()
    if totals.empty:
        calls = load_onoff_calls()
        if not calls.empty:
            calls["TEL"] = _clean_tel_db(calls["TEL"])
            calls = calls[calls["TEL"].isin(db_tels)]
            totals = (
                calls.groupby("TEL", as_index=False)["Duration_Seconds"]
                .sum()
                .rename(columns={"Duration_Seconds": "Total_Duration_Seconds"})
            )
            totals["Total_Duration"] = totals["Total_Duration_Seconds"].map(_format_duration)
    else:
        totals = totals[totals["TEL"].isin(db_tels)].copy()

    if totals.empty:
        out = df.copy()
        out["Total_Duration_Seconds"] = 0
        out["Total_Duration"] = "00:00:00"
        calls = load_onoff_calls()
        if not calls.empty:
            calls["TEL"] = _clean_tel_db(calls["TEL"])
            calls = calls[calls["TEL"].isin(db_tels)]
        last_calls = last_onoff_call_durations(calls, db_tels=db_tels)
        if not last_calls.empty:
            out = out.merge(last_calls, on="TEL", how="left")
        if "Duree_Dernier_Appel_Sec" not in out.columns:
            out["Duree_Dernier_Appel_Sec"] = 0
        else:
            out["Duree_Dernier_Appel_Sec"] = out["Duree_Dernier_Appel_Sec"].fillna(0).astype(int)
        if "Duree_Dernier_Appel" not in out.columns:
            out["Duree_Dernier_Appel"] = "00:00:00"
        else:
            out["Duree_Dernier_Appel"] = out["Duree_Dernier_Appel"].fillna("00:00:00")
        return out, {
            "onoff_calls_rows": storage.count_onoff_rows(),
            "onoff_tels_in_file": int(last_calls["TEL"].nunique()) if not last_calls.empty else 0,
            "onoff_tels_matched": int((out["Total_Duration_Seconds"] > 0).sum()),
            "onoff_tels_without_duration": int((out["Total_Duration_Seconds"] == 0).sum()),
            "onoff_total_duration_seconds": 0,
            "onoff_files_read": 0,
            "onoff_files_failed": 0,
            "onoff_per_file": [],
            "onoff_source": "store_empty",
        }

    out = df.merge(
        totals[["TEL", "Total_Duration_Seconds", "Total_Duration"]],
        on="TEL",
        how="left",
    )
    out["Total_Duration_Seconds"] = out["Total_Duration_Seconds"].fillna(0).astype(int)
    out["Total_Duration"] = out["Total_Duration"].fillna("00:00:00")

    calls = load_onoff_calls()
    if not calls.empty:
        calls["TEL"] = _clean_tel_db(calls["TEL"])
        calls = calls[calls["TEL"].isin(db_tels)]
    last_calls = last_onoff_call_durations(calls, db_tels=db_tels)
    if not last_calls.empty:
        out = out.merge(last_calls, on="TEL", how="left")
    if "Duree_Dernier_Appel_Sec" not in out.columns:
        out["Duree_Dernier_Appel_Sec"] = 0
    else:
        out["Duree_Dernier_Appel_Sec"] = out["Duree_Dernier_Appel_Sec"].fillna(0).astype(int)
    if "Duree_Dernier_Appel" not in out.columns:
        out["Duree_Dernier_Appel"] = "00:00:00"
    else:
        out["Duree_Dernier_Appel"] = out["Duree_Dernier_Appel"].fillna("00:00:00")

    stats = {
        "onoff_calls_rows": storage.count_onoff_rows(),
        "onoff_tels_in_file": int(totals["TEL"].nunique()),
        "onoff_tels_matched": int((out["Total_Duration_Seconds"] > 0).sum()),
        "onoff_tels_without_duration": int((out["Total_Duration_Seconds"] == 0).sum()),
        "onoff_total_duration_seconds": int(out["Total_Duration_Seconds"].sum()),
        "onoff_last_call_matched": int((out["Duree_Dernier_Appel_Sec"] > 0).sum()),
        "onoff_last_call_rows": int(len(last_calls)) if not last_calls.empty else 0,
        "onoff_files_read": 1,
        "onoff_files_failed": 0,
        "onoff_per_file": [{"file": f"store/{storage.backend_label()}", "type": "onoff_totals"}],
        "onoff_source": "onoff_totals+calls",
    }
    return out, stats


def frames_to_buffer(df: pd.DataFrame, *, name: str = "data.xlsx") -> io.BytesIO:
    """Serialize a dataframe to an in-memory Excel buffer for process_data()."""
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    buffer.name = name  # type: ignore[attr-defined]
    return buffer


def process_merged_store() -> tuple[pd.DataFrame, dict, dict]:
    """Build the full recyclage dataset from the persisted merged store."""
    from engine.processor import attach_repondeur_profiles, process_data

    latest, pipeline_stats = process_data(
        df_db=load_db(),
        df_hist=load_history(),
        return_stats=True,
    )
    latest, onoff_stats = attach_store_onoff(latest)
    latest = attach_repondeur_profiles(latest, load_history())
    return latest, pipeline_stats, onoff_stats


def merge_master_and_daily(
    *,
    master_db: str | Path | BinaryIO | None = None,
    master_hist: str | Path | BinaryIO | None = None,
    master_onoff: list[str | Path | BinaryIO] | None = None,
    daily_db: str | Path | BinaryIO | None = None,
    daily_hist: str | Path | BinaryIO | None = None,
    daily_onoff: list[str | Path | BinaryIO] | None = None,
    allow_new_tels: bool = False,
) -> dict[str, Any]:
    """Load master, merge daily updates, return stats + export preview."""
    if not (master_db and master_hist):
        raise ValueError(
            "La fusion exige la DB master et l'historique master. "
            "Uploadez les deux fichiers master dans la section Fusion."
        )
    if not daily_db and not daily_hist and not daily_onoff:
        raise ValueError("Fournissez au moins un fichier du jour (DB, historique ou Onoff).")

    report: dict[str, Any] = {}
    report["master"] = initialize_store(
        master_db,
        master_hist,
        None,
        label="initialisation master",
    )

    report["daily"] = apply_daily_update(
        daily_db=daily_db,
        daily_hist=daily_hist,
        daily_onoff=None,
        allow_new_tels=allow_new_tels,
        label="fusion quotidienne",
    )

    combined_onoff: list[str | Path | BinaryIO] = []
    if master_onoff:
        combined_onoff.extend(master_onoff)
    if daily_onoff:
        combined_onoff.extend(daily_onoff)
    if combined_onoff:
        report["onoff"] = _save_merged_onoff(combined_onoff, append=False)

    report["store"] = get_store_stats()
    latest, pipeline_stats, onoff_stats = process_merged_store()
    report["export_preview"] = {
        "processed_rows": len(latest),
        "unique_tels": int(latest["TEL"].nunique()) if not latest.empty else 0,
        "by_status": latest["Status_Category"].value_counts().to_dict() if not latest.empty else {},
        "pipeline": pipeline_stats,
        "onoff": onoff_stats,
    }
    return report


def export_full_recyclage(
    *,
    fichier_filter: list[str] | None = None,
    fichier_filter_mode: str = "include",
) -> tuple[bytes, dict[str, Any]]:
    """Build the complete colored recyclage workbook from the merged store."""
    from engine.processor import ALL_COLORS, DEFAULT_STATUS_MAPPING, export_excel, prepare_export_data

    latest, pipeline_stats, onoff_stats = process_merged_store()
    if latest.empty:
        raise ValueError("Aucune donnée après fusion. Vérifiez les fichiers master.")

    rows_before = len(latest)
    if fichier_filter:
        latest = apply_fichier_filter(
            latest,
            fichier_filter,
            mode=fichier_filter_mode,
        )
    if latest.empty:
        raise ValueError(
            "Aucune ligne après filtre FICHIER. Élargissez la sélection ou désactivez le filtre."
        )

    all_statuses = sorted(DEFAULT_STATUS_MAPPING.values())
    matching, filtered = prepare_export_data(
        latest,
        selected_statuses=all_statuses,
        selected_colors=ALL_COLORS,
    )
    excel_bytes = export_excel(
        latest,
        selected_statuses=all_statuses,
        selected_colors=ALL_COLORS,
    )
    summary = {
        "total_processed": len(latest),
        "total_before_fichier_filter": rows_before,
        "total_matching": len(matching),
        "total_exported": len(filtered),
        "fichier_filter": fichier_filter or [],
        "fichier_filter_mode": fichier_filter_mode,
        "rows_removed_by_fichier_filter": rows_before - len(latest),
        "by_status": filtered["Status_Category"].value_counts().to_dict(),
        "by_color": filtered["Color"].value_counts().to_dict(),
        "by_status_color": (
            filtered.groupby(["Status_Category", "Color"])
            .size()
            .reset_index(name="Lignes")
            .to_dict("records")
        ),
        "pipeline": pipeline_stats,
        "onoff_stats": onoff_stats,
    }
    return excel_bytes, summary


def _load_vente_baseline_storage() -> pd.DataFrame:
    _ensure_storage()
    if hasattr(storage, "load_vente_baseline"):
        return storage.load_vente_baseline()
    return pd.DataFrame(columns=["TEL", "Statut", "Couleur"])


def _replace_vente_baseline_storage(df: pd.DataFrame) -> int:
    _ensure_storage()
    if hasattr(storage, "replace_vente_baseline"):
        return storage.replace_vente_baseline(df)
    raise RuntimeError("Fonction replace_vente_baseline indisponible. Redémarrez Streamlit.")


def _append_vente_results_storage(df: pd.DataFrame, *, batch_id: str, analyzed_at: str) -> int:
    _ensure_storage()
    if hasattr(storage, "append_vente_results"):
        return storage.append_vente_results(df, batch_id=batch_id, analyzed_at=analyzed_at)
    raise RuntimeError("Fonction append_vente_results indisponible. Redémarrez Streamlit.")


def _load_vente_results_storage() -> pd.DataFrame:
    _ensure_storage()
    if hasattr(storage, "load_vente_results"):
        return storage.load_vente_results()
    return pd.DataFrame()


def capture_vente_baseline_from_store() -> dict[str, Any]:
    """Snapshot current recyclage statuses before a daily DB update."""
    from engine.vente_tracking import baseline_from_store_latest

    if not store_exists():
        raise FileNotFoundError("Base non initialisée.")
    baseline = baseline_from_store_latest(load_db(), load_history())
    count = _replace_vente_baseline_storage(baseline)
    return {
        "baseline_rows": count,
        "captured_at": datetime.now().isoformat(timespec="seconds"),
    }


def get_vente_baseline_count() -> int:
    _ensure_storage()
    if hasattr(storage, "count_vente_baseline"):
        return int(storage.count_vente_baseline())
    return 0


def load_vente_baseline() -> pd.DataFrame:
    return _load_vente_baseline_storage()


def save_vente_tracking_batch(
    result: dict[str, Any],
    *,
    batch_id: str | None = None,
) -> int:
    detail = result.get("detail", pd.DataFrame())
    if detail.empty:
        return 0
    batch = batch_id or datetime.now().strftime("%Y-%m-%d")
    analyzed_at = str(result.get("analyzed_at", datetime.now().isoformat(timespec="seconds")))
    return _append_vente_results_storage(detail, batch_id=batch, analyzed_at=analyzed_at)


def load_vente_tracking_history() -> pd.DataFrame:
    return _load_vente_results_storage()
