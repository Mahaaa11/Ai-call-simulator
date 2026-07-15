#!/usr/bin/env python3
"""Merge Onoff files into the store and generate the full recyclage export."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "onoff_files",
        nargs="+",
        help="Onoff exports (b2b reports and/or onoff_merged_totals.xlsx)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing Onoff store instead of replacing it",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output Excel path (default: ~/Downloads/Recyclage_Data_Client_<timestamp>.xlsx)",
    )
    parser.add_argument(
        "--fichier",
        action="append",
        default=None,
        help="Optional FICHIER filter (repeatable)",
    )
    args = parser.parse_args()

    sources = [Path(p) for p in args.onoff_files]
    for path in sources:
        if not path.exists():
            raise SystemExit(f"Fichier introuvable : {path}")

    print("Fusion Onoff…")
    onoff_stats = database.import_onoff_sources(
        sources,
        append=args.append,
        label="import onoff script",
    )
    print(
        f"  {onoff_stats['onoff_totals_rows']:,} TEL Onoff · "
        f"{onoff_stats['onoff_rows']:,} appels · "
        f"durée totale {onoff_stats['onoff_total_duration_seconds']:,} sec"
    )

    print("Génération export recyclage…")
    excel_bytes, summary = database.export_full_recyclage(fichier_filter=args.fichier)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    output = args.output or Path.home() / "Downloads" / f"Recyclage_Data_Client_{stamp}.xlsx"
    output.write_bytes(excel_bytes)

    onoff = summary.get("onoff_stats", {})
    print(f"Export écrit : {output}")
    print(f"  {summary['total_exported']:,} lignes exportées")
    print(
        f"  {onoff.get('onoff_tels_matched', 0):,} TEL avec durée Onoff · "
        f"{onoff.get('onoff_tels_without_duration', 0):,} sans durée Onoff"
    )


if __name__ == "__main__":
    main()
