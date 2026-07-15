"""Export status sheet / Red rows sorted by LAST call duration (descending)."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from engine.processor import (  # noqa: E402
    DEFAULT_COLOR_FILLS,
    _clean_tel_db,
    _clean_tel_hist_initial,
    _format_duration,
    _parse_date_column,
)


def _last_call_duration_by_tel(history_path: Path, *, status_code: str | None = None) -> pd.DataFrame:
    hist = pd.read_csv(history_path, encoding="latin-1", sep=";", dtype=str)
    hist["TEL"] = _clean_tel_hist_initial(hist["TEL"].astype(str))
    hist["DATE"] = _parse_date_column(hist["DATE"])
    hist["DUREE_SEC"] = pd.to_numeric(hist["DUREE"], errors="coerce").fillna(0).astype(int)

    if status_code is not None:
        hist = hist[hist["STATUS"] == status_code]

    if "HEURE" in hist.columns:
        heure = pd.to_numeric(hist["HEURE"], errors="coerce").fillna(0).astype(int).astype(str).str.zfill(4)
        hist["DATETIME"] = pd.to_datetime(
            hist["DATE"].dt.strftime("%Y-%m-%d") + " " + heure.str[:2] + ":" + heure.str[2:],
            errors="coerce",
        )
    else:
        hist["DATETIME"] = hist["DATE"]

    last_calls = (
        hist.sort_values("DATETIME")
        .groupby("TEL", as_index=False)
        .tail(1)[["TEL", "DUREE_SEC", "LIB_STATUS", "DATETIME"]]
        .rename(
            columns={
                "DUREE_SEC": "Duree_Dernier_Appel_Sec",
                "LIB_STATUS": "Statut_Dernier_Appel",
                "DATETIME": "Date_Dernier_Appel",
            }
        )
    )
    last_calls["Duree_Dernier_Appel"] = last_calls["Duree_Dernier_Appel_Sec"].map(_format_duration)
    return last_calls


STATUS_CODE_BY_SHEET = {
    "Refus": "2",
    "Pas de collaboration": "4",
}


def export_sheet_red_sorted(
    source_path: Path,
    history_path: Path,
    output_path: Path,
    *,
    sheet_name: str = "Refus",
) -> int:
    df = pd.read_excel(source_path, sheet_name=sheet_name, header=5)
    red = df[df["Color"].astype(str) == "Red"].copy()
    red["TEL"] = _clean_tel_db(red["TEL"].astype(str))

    status_code = STATUS_CODE_BY_SHEET.get(sheet_name)
    last_calls = _last_call_duration_by_tel(history_path, status_code=status_code)
    red = red.merge(last_calls, on="TEL", how="left")

    # Durée du dernier appel = colonne DUREE de la fiche (pas la durée totale cumulée)
    row_duree = pd.to_numeric(red["DUREE"], errors="coerce").fillna(0).astype(int)
    red["Duree_Dernier_Appel_Sec"] = row_duree
    red["Duree_Dernier_Appel"] = red["Duree_Dernier_Appel_Sec"].map(_format_duration)

    red = red.sort_values("Duree_Dernier_Appel_Sec", ascending=True)

    summary = pd.DataFrame(
        {
            "Metric": [
                "Unique TEL",
                "Lignes",
                "Dernier appel max (sec)",
                "Dernier appel moyen (sec)",
            ],
            "Value": [
                red["TEL"].nunique(),
                len(red),
                int(red["Duree_Dernier_Appel_Sec"].max()),
                round(red["Duree_Dernier_Appel_Sec"].mean(), 1),
            ],
        }
    )

    extra_cols = ["Duree_Dernier_Appel", "Statut_Dernier_Appel", "Date_Dernier_Appel"]
    base_cols = [c for c in red.columns if c not in {"Duree_Dernier_Appel_Sec", *extra_cols}]
    export_df = red[base_cols + [c for c in extra_cols if c in red.columns]]

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name=sheet_name[:31], index=False, startrow=0)
        export_df.to_excel(writer, sheet_name=sheet_name[:31], index=False, startrow=5)

    buffer.seek(0)
    wb = load_workbook(buffer)
    fills = {
        name: PatternFill(start_color=hex_color, end_color=hex_color, fill_type="solid")
        for name, hex_color in DEFAULT_COLOR_FILLS.items()
    }

    for ws in wb.worksheets:
        headers = [c.value for c in ws[6]]
        if "Color" not in headers:
            continue
        color_col = headers.index("Color") + 1
        for row in range(7, ws.max_row + 1):
            cell = ws.cell(row, color_col)
            fill = fills.get(cell.value)
            if fill:
                cell.fill = fill

        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass
            ws.column_dimensions[column_letter].width = min(max_length + 2, 40)

    wb.save(output_path)
    return len(red)


if __name__ == "__main__":
    source = Path("/Users/macbookpro/Downloads/Recyclage_Data_Client (16).xlsx")
    history = Path("/Users/macbookpro/Downloads/export_histo_data_client_07072026.csv")

    jobs = [
        ("Refus", "/Users/macbookpro/Downloads/Recyclage_Refus_Red_Tri_Duree.xlsx"),
        ("Pas de collaboration", "/Users/macbookpro/Downloads/Recyclage_PasCollab_Red_Tri_Duree.xlsx"),
    ]
    for sheet, out in jobs:
        count = export_sheet_red_sorted(source, history, Path(out), sheet_name=sheet)
        print(f"{sheet}: {count:,} lignes · tri par durée du DERNIER appel → {out}")
