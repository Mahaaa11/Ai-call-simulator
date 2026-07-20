"""Lead & Connect Analytics — all-in-one data analytics platform."""

from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import engine.database as database
import engine.dashboard as dashboard
import engine.data_client_dashboard as data_client_dashboard
import engine.forecast as forecast
import engine.processor as processor
import engine.vente_tracking as vente_tracking
from ui.data_client_board import render_data_client_board
from ui.ventes_board import render_ventes_page
from ui.app_shell import (
    inject_global_theme,
    render_global_data_source,
    render_navigation,
    render_overview_board,
    render_section_header,
    render_sidebar_brand,
)
import engine.analytics_hub as analytics_hub
import engine.ventes_analytics as ventes_analytics

ALL_COLORS = processor.ALL_COLORS
DEFAULT_STATUS_MAPPING = processor.DEFAULT_STATUS_MAPPING
export_excel = processor.export_excel
prepare_export_data = processor.prepare_export_data
process_data = processor.process_data
attach_onoff_durations = processor.attach_onoff_durations
_format_duration = processor._format_duration
NOT_FOUND_LABEL = vente_tracking.NOT_FOUND_LABEL

BUCKET_BAR_HEX = {
    **{k: f"#{v}" for k, v in processor.DEFAULT_COLOR_FILLS.items()},
    "Unknown": "#A6A6A6",
}


def _render_colored_bucket_bar_chart(by_color: dict[str, int]) -> None:
    """Bar chart with one bar color per ancienneté bucket."""
    import plotly.graph_objects as go

    rows = [
        {
            "Bucket": dashboard.COLOR_LABELS_FR.get(color, color),
            "Contacts": int(by_color.get(color, 0)),
            "ColorKey": color,
        }
        for color in dashboard.COLOR_ORDER
        if int(by_color.get(color, 0)) > 0 or color != "Unknown"
    ]
    bucket_df = pd.DataFrame(rows)
    if bucket_df.empty:
        st.info("Aucun contact dans les buckets couleur.")
        return

    bar_colors = [BUCKET_BAR_HEX.get(key, "#A6A6A6") for key in bucket_df["ColorKey"]]
    fig = go.Figure(
        data=[
            go.Bar(
                x=bucket_df["Bucket"],
                y=bucket_df["Contacts"],
                marker={"color": bar_colors},
                text=bucket_df["Contacts"].map(lambda n: f"{n:,}".replace(",", "\u202f")),
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        height=380,
        margin={"l": 24, "r": 16, "t": 16, "b": 72},
        xaxis_title="",
        yaxis_title="Contacts",
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, system-ui, sans-serif", "color": "#00234E"},
    )
    st.plotly_chart(fig, use_container_width=True)


def _store_cache_token() -> str:
    if not database.store_exists():
        return "no-store"
    stats = database.get_store_stats()
    return "|".join(
        str(stats.get(k, ""))
        for k in ("last_update", "hist_rows", "db_tels", "onoff_rows")
    )


def _needs_analytics_refresh(
    cache_name: str,
    *,
    refresh_clicked: bool,
    token: str,
    **filters: Any,
) -> bool:
    filter_key = "|".join(f"{k}={filters[k]!r}" for k in sorted(filters))
    full_key = f"{token}|{filter_key}"
    if refresh_clicked or st.session_state.get(f"{cache_name}_key") != full_key:
        st.session_state[f"{cache_name}_key"] = full_key
        return True
    return cache_name not in st.session_state


def _format_duration_label(seconds: int) -> str:
    return _format_duration(int(seconds))


def _render_vente_daily_tracking(
    *,
    baseline_mode: str,
    baseline_recyclage_file,
    baseline_client_files: list,
    daily_vente_files: list,
    save_to_history: bool,
    analyze_btn: bool,
    capture_baseline_btn: bool,
) -> None:
    st.markdown(
        "**Suivi quotidien** — pour chaque vente (`STATUS = 1` dans `export_data_client`), "
        "retrouver le statut d'origine dans l'export recyclage ou la base **avant** la journée."
    )

    baseline_frames: list[pd.DataFrame] = []
    baseline_label = baseline_mode

    if capture_baseline_btn:
        try:
            with st.spinner("Capture du baseline depuis la base…"):
                snap = database.capture_vente_baseline_from_store()
            st.success(
                f"Baseline enregistré : {snap['baseline_rows']:,} TEL "
                f"({snap['captured_at']})."
            )
        except Exception as exc:
            st.error(f"Capture baseline : {exc}")

    if baseline_mode in ("store_snapshot", "store_snapshot+upload"):
        stored = database.load_vente_baseline()
        if not stored.empty:
            baseline_frames.append(stored[["TEL", "Statut", "Couleur"]])
            baseline_label = f"snapshot base ({len(stored):,} TEL)"
        elif baseline_mode == "store_snapshot":
            st.warning(
                "Aucun snapshot en base. Cliquez **Capturer baseline** avant la MAJ du jour, "
                "ou uploadez un export recyclage."
            )

    if baseline_mode in ("recyclage_upload", "store_snapshot+upload") and baseline_recyclage_file:
        try:
            frame = vente_tracking.baseline_from_recyclage_export(baseline_recyclage_file)
            baseline_frames.append(frame)
            baseline_label = f"export recyclage ({len(frame):,} TEL)"
        except Exception as exc:
            st.error(f"Lecture export recyclage : {exc}")

    if baseline_mode in ("client_upload", "store_snapshot+upload") and baseline_client_files:
        for uploaded in baseline_client_files:
            try:
                df = processor._read_excel(uploaded, is_history=False)
                baseline_frames.append(vente_tracking.baseline_from_client_db(df))
            except Exception as exc:
                st.error(f"Lecture {uploaded.name} : {exc}")
        if baseline_client_files:
            baseline_label = f"fichiers client ({len(baseline_client_files)} fichier(s))"

    baseline = vente_tracking.merge_baseline_frames(baseline_frames)

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Baseline TEL", f"{len(baseline):,}")
    col_b.metric("Snapshot base", f"{database.get_vente_baseline_count():,}")

    history = database.load_vente_tracking_history()
    if not history.empty:
        col_c.metric("Analyses enregistrées", f"{history['Batch_id'].nunique():,}")
        col_d.metric("Ventes historisées", f"{len(history):,}")

    if not analyze_btn:
        st.info(
            "Workflow : 1) Capturer le baseline **avant** les appels (ou uploader l'export recyclage du matin). "
            "2) Uploader les `export_data_client` du jour. 3) **Analyser les ventes**."
        )
        return

    if not daily_vente_files:
        st.warning("Uploadez au moins un export client du jour (`export_data_client`).")
        return
    if baseline.empty:
        st.warning("Aucun baseline disponible. Capturez ou uploadez l'export recyclage.")
        return

    try:
        vente_sources = []
        for uploaded in daily_vente_files:
            name = uploaded.name.lower()
            if "0807" in name or "08-07" in name or "08_07" in name:
                day = "08/07"
            elif "0907" in name or "09-07" in name or "09_07" in name:
                day = "09/07"
            else:
                day = uploaded.name.rsplit(".", 1)[0][-10:]
            vente_sources.append((uploaded, day))

        with st.spinner("Analyse des ventes…"):
            ventes = vente_tracking.extract_ventes_from_client_exports(vente_sources)
            result = vente_tracking.compute_vente_origin_tracking(
                baseline,
                ventes,
                baseline_source=baseline_label,
            )
            if save_to_history:
                saved = database.save_vente_tracking_batch(result)
                st.caption(f"{saved} ligne(s) enregistrée(s) dans l'historique.")
    except Exception as exc:
        st.error(f"Analyse ventes : {exc}")
        return

    totals = result["totals"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Ventes (lignes)", f"{totals['vente_rows']:,}")
    m2.metric("TEL uniques", f"{totals['vente_unique_tels']:,}")
    m3.metric("Matchées", f"{totals['matched_rows']:,}")
    m4.metric(
        "Taux match",
        f"{round(100 * totals['matched_rows'] / max(totals['vente_rows'], 1), 1)}%",
    )

    by_origin = result.get("summary_by_origin", pd.DataFrame())
    by_day = result.get("summary_by_day", pd.DataFrame())
    detail = result.get("detail", pd.DataFrame())

    if not by_origin.empty:
        st.markdown("**Statut d'origine → Vente**")
        chart_df = by_origin.set_index("Statut_origine")
        if "Taux_%" in chart_df.columns:
            st.bar_chart(chart_df["Taux_%"])
        st.dataframe(by_origin, hide_index=True, use_container_width=True)

    if not by_day.empty:
        st.markdown("**Ventes par jour**")
        st.dataframe(by_day, hide_index=True, use_container_width=True)

    if not detail.empty:
        st.markdown("**Détail des ventes**")
        show_cols = [
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
            ]
            if c in detail.columns
        ]
        st.dataframe(detail[show_cols], hide_index=True, use_container_width=True)

        export_df = vente_tracking.tracking_detail_for_export(result)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, sheet_name="Ventes", index=False)
            if not by_origin.empty:
                by_origin.to_excel(writer, sheet_name="Synthèse_origine", index=False)
            if not by_day.empty:
                by_day.to_excel(writer, sheet_name="Synthèse_jour", index=False)
        st.download_button(
            "Télécharger le rapport ventes",
            data=buffer.getvalue(),
            file_name=f"ventes_tracking_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if not history.empty:
        with st.expander("Historique des analyses enregistrées"):
            hist_summary = (
                history.groupby(["Batch_id", "Jour_Vente", "Statut_origine"])
                .size()
                .reset_index(name="Ventes")
                .sort_values(["Batch_id", "Ventes"], ascending=[False, False])
            )
            st.dataframe(hist_summary.head(200), hide_index=True, use_container_width=True)


def _render_data_client_dashboard(
    *,
    use_store: bool,
    db_file,
    hist_file,
    year: int,
    month: int | None,
    colors: list[str] | None,
    statuses: list[str] | None,
    refresh: bool,
) -> None:
    token = _store_cache_token() if use_store else f"upload:{getattr(db_file, 'name', '')}:{getattr(hist_file, 'name', '')}"
    if not _needs_analytics_refresh(
        "data_client_metrics",
        refresh_clicked=refresh,
        token=token,
        year=year,
        month=month,
        colors=tuple(colors or []),
        statuses=tuple(statuses or []),
        use_store=use_store,
    ):
        render_data_client_board(st.session_state["data_client_metrics"])
        return

    try:
        if use_store:
            if not database.store_exists():
                st.warning(
                    "Base non initialisée. Allez dans **Base de données** pour importer les fichiers master."
                )
                return
            with st.spinner("Calcul du tableau de bord Data Client…"):
                metrics = data_client_dashboard.compute_data_client_dashboard(
                    database.load_db(),
                    database.load_history(),
                    year=year,
                    month=month,
                    colors=colors,
                    statuses=statuses,
                )
        else:
            if not db_file or not hist_file:
                st.info("Chargez la base client et l'historique, ou activez la base enregistrée.")
                return
            with st.spinner("Calcul du tableau de bord Data Client…"):
                df_db = processor._read_excel(db_file, is_history=False)
                if str(hist_file.name).lower().endswith(".csv"):
                    df_hist = processor._read_csv(hist_file)
                else:
                    df_hist = processor._read_excel(hist_file, is_history=True)
                metrics = data_client_dashboard.compute_data_client_dashboard(
                    df_db,
                    df_hist,
                    year=year,
                    month=month,
                    colors=colors,
                    statuses=statuses,
                )
    except Exception as exc:
        st.error(f"Erreur tableau de bord Data Client : {exc}")
        return

    if metrics["total_fiches"] == 0:
        st.warning("Aucune fiche dans la Data Client après filtres.")
        return

    excel_bytes = render_data_client_board(metrics)
    st.session_state["data_client_metrics"] = metrics
    if excel_bytes:
        st.session_state["data_client_excel_bytes"] = excel_bytes


def _load_analytics_frames(
    *,
    use_store: bool,
    db_file,
    hist_file,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    if use_store:
        if not database.store_exists():
            return None
        return database.load_db(), database.load_history()
    if not db_file or not hist_file:
        return None
    df_db = processor._read_excel(db_file, is_history=False)
    if str(hist_file.name).lower().endswith(".csv"):
        df_hist = processor._read_csv(hist_file)
    else:
        df_hist = processor._read_excel(hist_file, is_history=True)
    return df_db, df_hist


def _render_overview_dashboard(
    *,
    use_store: bool,
    db_file,
    hist_file,
    year: int,
    refresh: bool = False,
) -> None:
    token = _store_cache_token() if use_store else f"upload:{getattr(db_file, 'name', '')}:{getattr(hist_file, 'name', '')}"
    if not _needs_analytics_refresh(
        "overview_metrics",
        refresh_clicked=refresh,
        token=token,
        year=year,
        use_store=use_store,
    ):
        render_overview_board(st.session_state["overview_metrics"])
        return

    frames = _load_analytics_frames(use_store=use_store, db_file=db_file, hist_file=hist_file)
    if frames is None:
        st.info(
            "Activez la **base persistante** ou uploadez la base client et l'historique "
            "dans la barre latérale pour charger la vue d'ensemble."
        )
        return
    try:
        with st.spinner("Calcul des indicateurs globaux…"):
            store_stats = database.get_store_stats() if database.store_exists() else {}
            metrics = analytics_hub.compute_overview_metrics(
                frames[0],
                frames[1],
                year=year,
                store_stats=store_stats,
            )
        render_overview_board(metrics)
        st.session_state["overview_metrics"] = metrics
    except Exception as exc:
        st.error(f"Erreur vue d'ensemble : {exc}")


def _render_ventes_analytics(
    *,
    use_store: bool,
    db_file,
    hist_file,
    year: int,
    month: int | None,
    prior_colors: list[str] | None,
    prior_statuses: list[str] | None,
    vente_track_config: dict | None,
) -> None:
    frames = _load_analytics_frames(use_store=use_store, db_file=db_file, hist_file=hist_file)
    if frames is None:
        st.info(
            "Activez la **base persistante** ou uploadez la base client et l'historique "
            "dans la barre latérale."
        )
        return

    tab_analyse, tab_quotidien = st.tabs(["Analyse des ventes", "Suivi quotidien"])

    with tab_analyse:
        try:
            with st.spinner("Analyse des parcours vente…"):
                metrics = ventes_analytics.compute_ventes_analytics(
                    frames[0],
                    frames[1],
                    year=year,
                    month=month,
                    prior_colors=prior_colors,
                    prior_statuses=prior_statuses,
                )
            excel_bytes = render_ventes_page(metrics)
            if excel_bytes:
                st.session_state["ventes_excel_bytes"] = excel_bytes
        except Exception as exc:
            st.error(f"Erreur analyse ventes : {exc}")

    with tab_quotidien:
        if vente_track_config:
            _render_vente_daily_tracking(**vente_track_config)
        else:
            st.info("Configuration suivi quotidien indisponible.")


def _render_performance_dashboard(
    *,
    use_store: bool,
    db_file,
    hist_file,
    stale_days: int,
    retry_days: int,
    vente_track_config: dict | None = None,
    refresh: bool = False,
) -> None:
    token = _store_cache_token() if use_store else f"upload:{getattr(db_file, 'name', '')}:{getattr(hist_file, 'name', '')}"
    if _needs_analytics_refresh(
        "performance_metrics",
        refresh_clicked=refresh,
        token=token,
        stale_days=stale_days,
        retry_days=retry_days,
        use_store=use_store,
    ):
        try:
            if use_store:
                if not database.store_exists():
                    st.warning(
                        "Base non initialisée. Allez dans **Base de données** pour importer les fichiers master."
                    )
                    return
                with st.spinner("Calcul des indicateurs…"):
                    metrics = dashboard.compute_dashboard(
                        database.load_db(),
                        database.load_history(),
                        stale_days=stale_days,
                        retry_days=retry_days,
                    )
            else:
                if not db_file or not hist_file:
                    st.info("Chargez la base client et l'historique, ou activez la base enregistrée.")
                    return
                with st.spinner("Calcul des indicateurs…"):
                    df_db = processor._read_excel(db_file, is_history=False)
                    if str(hist_file.name).lower().endswith(".csv"):
                        df_hist = processor._read_csv(hist_file)
                    else:
                        df_hist = processor._read_excel(hist_file, is_history=True)
                    metrics = dashboard.compute_dashboard(
                        df_db,
                        df_hist,
                        stale_days=stale_days,
                        retry_days=retry_days,
                    )
        except Exception as exc:
            st.error(f"Erreur tableau de bord : {exc}")
            return

        if metrics["contacts_by_bucket"]["total_contacts"] == 0:
            st.warning("Aucun contact exploitable après traitement.")
            return
        st.session_state["performance_metrics"] = metrics
    else:
        metrics = st.session_state["performance_metrics"]

    st.subheader("Vue d'ensemble")
    vente = metrics.get("vente_conversion", {})
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Contacts actifs", f"{metrics['contacts_by_bucket']['total_contacts']:,}")
    c2.metric("Ventes (statut 1)", f"{vente.get('total_ventes', 0):,}")
    c3.metric(
        "Taux vente / TEL",
        f"{vente.get('overall_vente_rate_pct', 0)}%",
    )
    c4.metric(
        "Obsolètes",
        f"{metrics['stale_contacts']['stale_count']:,}",
        f"{metrics['stale_contacts']['stale_pct']}%",
    )
    c5.metric("Éligibles recyclage", f"{metrics['stale_contacts']['recyclable_count']:,}")
    c6.metric(
        "Taux positif",
        f"{metrics['conversion']['positive_rate_pct']}%"
        if metrics["conversion"]["available"]
        else "—",
    )

    tab_daily, tab_transitions, tab_vente, tab_vente_track, tab_buckets, tab_stale, tab_dupes, tab_retry, tab_outcomes = st.tabs(
        [
            "Résultats par jour",
            "Parcours statuts",
            "Conversion Vente",
            "Suivi ventes quotidien",
            "Contacts par bucket",
            "Contacts obsolètes",
            "Doublons",
            "Relances par date",
            "Résultats recyclage",
        ]
    )

    with tab_daily:
        st.markdown("**Résultats par jour** — nombre d'appels aboutissant à chaque statut.")
        daily = vente.get("daily_outcomes", pd.DataFrame())
        daily_conv = vente.get("daily_conversion", pd.DataFrame())
        if not daily.empty:
            d1, d2 = st.columns(2)
            with d1:
                st.markdown("**Ventes par jour (statut 1)**")
                if not daily_conv.empty:
                    chart = daily_conv.copy()
                    chart["Date"] = pd.to_datetime(chart["Date"])
                    st.line_chart(chart.set_index("Date")[["Ventes", "Appels"]])
                else:
                    st.info("Pas de ventes enregistrées.")
            with d2:
                st.markdown("**Taux de vente journalier**")
                if not daily_conv.empty:
                    rate_chart = daily_conv.copy()
                    rate_chart["Date"] = pd.to_datetime(rate_chart["Date"])
                    st.line_chart(rate_chart.set_index("Date")["Taux_Vente_%"])
            st.dataframe(daily, hide_index=True, use_container_width=True)
            with st.expander("Synthèse journalière (ventes + taux)"):
                st.dataframe(daily_conv, hide_index=True, use_container_width=True)
        else:
            st.info("Pas de résultats journaliers sur la période.")

    with tab_transitions:
        st.markdown(
            "Statut **précédent** → statut **résultat** sur l'appel suivant (même TEL). "
            "Permet de voir quel parcours mène à chaque résultat."
        )
        matrix = metrics.get("status_transitions", {}).get("matrix", pd.DataFrame())
        if not matrix.empty:
            top = matrix.head(30)
            st.dataframe(top, hide_index=True, use_container_width=True)
            pivot = matrix.pivot_table(
                index="Statut_précédent",
                columns="Statut_résultat",
                values="Transitions",
                aggfunc="sum",
                fill_value=0,
            )
            with st.expander("Matrice complète (heatmap)"):
                st.dataframe(pivot.astype(int), use_container_width=True)
        else:
            st.info("Pas assez d'historique pour calculer les transitions.")

    with tab_vente:
        st.markdown("**Conversion vers Vente (statut 1)**")
        v1, v2, v3 = st.columns(3)
        v1.metric("Total ventes", f"{vente.get('total_ventes', 0):,}")
        v2.metric("TEL uniques vendus", f"{vente.get('ventes_unique_tels', 0):,}")
        v3.metric("Taux vente / base TEL", f"{vente.get('overall_vente_rate_pct', 0)}%")

        prior = vente.get("conversion_by_prior_status", pd.DataFrame())
        if not prior.empty:
            st.markdown("**Quel statut précédent mène à la vente ?**")
            st.caption(
                "Taux = ventes après ce statut / nombre total de transitions depuis ce statut."
            )
            st.bar_chart(prior.set_index("Statut_précédent")["Taux_conversion_%"])
            st.dataframe(prior, hide_index=True, use_container_width=True)
        else:
            st.info("Aucune vente avec statut précédent identifiable.")

        vente_trans = vente.get("vente_transitions", pd.DataFrame())
        if not vente_trans.empty:
            with st.expander("Détail des ventes (statut précédent)"):
                show_cols = [
                    c
                    for c in [
                        "TEL",
                        "DATE",
                        "Prior_Status",
                        "Status_Category",
                        "LIB_STATUS",
                    ]
                    if c in vente_trans.columns
                ]
                st.dataframe(
                    vente_trans[show_cols].sort_values("DATE", ascending=False).head(500),
                    hide_index=True,
                    use_container_width=True,
                )

    with tab_vente_track:
        cfg = vente_track_config or {}
        _render_vente_daily_tracking(
            baseline_mode=cfg.get("baseline_mode", "store_snapshot+upload"),
            baseline_recyclage_file=cfg.get("baseline_recyclage_file"),
            baseline_client_files=cfg.get("baseline_client_files") or [],
            daily_vente_files=cfg.get("daily_vente_files") or [],
            save_to_history=cfg.get("save_to_history", True),
            analyze_btn=cfg.get("analyze_btn", False),
            capture_baseline_btn=cfg.get("capture_baseline_btn", False),
        )

    with tab_buckets:
        st.markdown("Répartition des contacts par ancienneté (couleur).")
        by_color = metrics["contacts_by_bucket"]["by_color"]
        _render_colored_bucket_bar_chart(by_color)
        st.dataframe(
            metrics["contacts_by_bucket"]["by_status_color"][
                ["Status_Category", "Couleur", "Contacts"]
            ].rename(
                columns={
                    "Status_Category": "Statut",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    with tab_stale:
        stale = metrics["stale_contacts"]
        s1, s2, s3 = st.columns(3)
        s1.metric(f"≥ {stale['threshold_days']} jours", f"{stale['stale_count']:,}")
        s2.metric("≥ 90 jours", f"{stale['very_stale_count']:,}")
        s3.metric("Verts/Bleus recyclables", f"{stale['recyclable_count']:,}")

        if stale["by_status"]:
            stale_status_df = pd.DataFrame(
                {"Statut": list(stale["by_status"].keys()), "Contacts": list(stale["by_status"].values())}
            ).sort_values("Contacts", ascending=False)
            st.bar_chart(stale_status_df.set_index("Statut"))
        else:
            st.info("Aucun contact obsolète pour ce seuil.")

    with tab_dupes:
        dupes = metrics["duplicates"]
        d1, d2, d3 = st.columns(3)
        d1.metric("TEL en double (base)", f"{dupes['db_duplicate_tels']:,}")
        d2.metric("Lignes en trop (base)", f"{dupes['db_extra_rows']:,}")
        d3.metric("Lignes dupliquées (historique)", f"{dupes['history_duplicate_rows']:,}")
        st.caption(
            f"Historique analysé : {dupes['history_total_rows']:,} lignes. "
            "Un doublon = même TEL, date, statut et heure."
        )

    with tab_retry:
        retry = metrics["retry_volume"]
        r1, r2 = st.columns(2)
        r1.metric(f"Appels ({retry['window_days']} j)", f"{retry['total_calls']:,}")
        r2.metric("Moyenne / jour", f"{retry['avg_calls_per_day']:,}")
        if not retry["by_date"].empty:
            chart_df = retry["by_date"].copy()
            chart_df["Date"] = pd.to_datetime(chart_df["Date"])
            st.line_chart(chart_df.set_index("Date")["Appels"])
            with st.expander("Détail par statut"):
                st.dataframe(retry["by_date_status"], hide_index=True, use_container_width=True)
        else:
            st.info("Pas d'appels sur la période sélectionnée.")

    with tab_outcomes:
        outcomes = metrics["outcomes"]
        o1, o2 = st.columns(2)
        with o1:
            st.markdown("**Statut actuel (dernier contact)**")
            if outcomes["current_by_status"]:
                current_df = pd.DataFrame(
                    {
                        "Statut": list(outcomes["current_by_status"].keys()),
                        "Contacts": list(outcomes["current_by_status"].values()),
                    }
                ).sort_values("Contacts", ascending=False)
                st.bar_chart(current_df.set_index("Statut"))
            else:
                st.info("Aucune donnée.")
        with o2:
            st.markdown("**Buckets recyclables (Vert/Bleu)**")
            if outcomes["recyclable_buckets_by_status"]:
                rec_df = pd.DataFrame(
                    {
                        "Statut": list(outcomes["recyclable_buckets_by_status"].keys()),
                        "Contacts": list(outcomes["recyclable_buckets_by_status"].values()),
                    }
                ).sort_values("Contacts", ascending=False)
                st.bar_chart(rec_df.set_index("Statut"))
            else:
                st.info("Aucun contact en bucket Vert/Bleu.")

        st.markdown(f"**Activité récente ({outcomes['recent_window_days']} derniers jours)**")
        if outcomes["recent_30d_by_status"]:
            recent_df = pd.DataFrame(
                {
                    "Statut": list(outcomes["recent_30d_by_status"].keys()),
                    "Appels": list(outcomes["recent_30d_by_status"].values()),
                }
            ).sort_values("Appels", ascending=False)
            st.dataframe(recent_df, hide_index=True, use_container_width=True)
        else:
            st.info("Pas d'activité récente enregistrée.")


SORT_PRIORITY_LABELS = {
    "oldest": "Plus anciennes (jours depuis dernier contact)",
    "duration": "Plus grande durée d'appel (Onoff)",
}


def _render_export_summary(summary: dict) -> None:
    """Affiche les tableaux de répartition après génération de l'export."""
    priority_label = SORT_PRIORITY_LABELS.get(
        summary.get("sort_priority", "oldest"),
        summary.get("sort_priority", "oldest"),
    )
    st.caption(f"Priorité de sélection : **{priority_label}**")

    if summary.get("limit_enabled"):
        scope_labels = {
            "per_status": "par statut (max par feuille)",
            "total_balanced": "total réparti entre statuts × couleurs",
            "total_oldest": "total global (plus anciens en priorité)",
            "custom": "quotas personnalisés statut × couleur",
        }
        scope_label = scope_labels.get(summary.get("limit_scope"), summary.get("limit_scope"))
        st.caption(
            f"Limite appliquée : {summary.get('max_rows', 0):,} contacts ({scope_label}). "
            f"Sélection par : {priority_label.lower()}."
        )

    col_status, col_color = st.columns(2)

    with col_status:
        st.subheader("Par statut")
        if summary.get("by_status"):
            status_df = (
                pd.DataFrame(
                    {
                        "Statut": list(summary["by_status"].keys()),
                        "Fiches": list(summary["by_status"].values()),
                    }
                )
                .sort_values("Fiches", ascending=False)
                .reset_index(drop=True)
            )
            st.dataframe(status_df, hide_index=True, use_container_width=True)
        else:
            st.info("Aucune fiche exportée.")

    with col_color:
        st.subheader("Par couleur")
        if summary.get("by_color"):
            color_df = (
                pd.DataFrame(
                    {
                        "Couleur": list(summary["by_color"].keys()),
                        "Fiches": list(summary["by_color"].values()),
                    }
                )
                .sort_values("Fiches", ascending=False)
                .reset_index(drop=True)
            )
            st.dataframe(color_df, hide_index=True, use_container_width=True)
        else:
            st.info("Aucune fiche exportée.")

    st.subheader("Détail par statut et couleur")
    if summary.get("by_status_color"):
        detail_df = pd.DataFrame(summary["by_status_color"]).rename(
            columns={"Status_Category": "Statut", "Color": "Couleur", "Lignes": "Fiches"}
        )
        pivot_df = (
            detail_df.pivot_table(
                index="Statut",
                columns="Couleur",
                values="Fiches",
                aggfunc="sum",
                fill_value=0,
            )
            .astype(int)
        )
        color_cols = [c for c in ALL_COLORS if c in pivot_df.columns]
        pivot_df = pivot_df.reindex(columns=color_cols, fill_value=0)
        pivot_df["Total"] = pivot_df.sum(axis=1)
        pivot_df = pivot_df.sort_values("Total", ascending=False)
        st.dataframe(pivot_df, use_container_width=True)

        with st.expander("Vue liste"):
            st.dataframe(
                detail_df.sort_values(["Statut", "Couleur"]),
                hide_index=True,
                use_container_width=True,
            )
    else:
        st.info("Aucune combinaison statut × couleur exportée.")


def _render_custom_quotas(
    selected_statuses: list[str],
    selected_colors: list[str],
    *,
    default_quota: int = 100,
    sort_priority: str = "oldest",
) -> dict[str, dict[str, int]]:
    priority_hint = (
        "les plus grandes durées d'appel"
        if sort_priority == "duration"
        else "les plus anciens contacts"
    )
    st.subheader("Quotas par statut et couleur")
    st.caption(
        "Indiquez combien de contacts exporter pour chaque combinaison. "
        f"0 = exclure. **{priority_hint.capitalize()}** sont pris en priorité dans chaque case."
    )

    quotas: dict[str, dict[str, int]] = {}
    header_cols = st.columns([2] + [1] * len(selected_colors))
    header_cols[0].markdown("**Statut**")
    for index, color in enumerate(selected_colors, start=1):
        header_cols[index].markdown(f"**{color}**")

    for status_index, status in enumerate(selected_statuses):
        row_cols = st.columns([2] + [1] * len(selected_colors))
        row_cols[0].write(status)
        quotas[status] = {}
        for color_index, color in enumerate(selected_colors):
            with row_cols[color_index + 1]:
                quotas[status][color] = int(
                    st.number_input(
                        f"{status} / {color}",
                        min_value=0,
                        value=default_quota,
                        step=10,
                        key=f"quota_{status_index}_{color_index}",
                        label_visibility="collapsed",
                    )
                )

    total_quota = sum(
        color_quota for color_map in quotas.values() for color_quota in color_map.values()
    )
    st.info(f"Total demandé : **{total_quota:,}** contacts")
    return quotas


def _render_forecast_quotas(
    available: dict[str, dict[str, int]],
    *,
    default_quota: int = 0,
    key_prefix: str = "fc",
) -> dict[str, dict[str, int]]:
    statuses = sorted(available.keys())
    colors = [color for color in ALL_COLORS if any(available[s].get(color, 0) > 0 for s in statuses)]
    if not colors:
        colors = ALL_COLORS

    st.subheader("Quotas par statut et couleur projetée")
    st.caption(
        "Indiquez combien de contacts exporter pour chaque case. "
        "Les quotas portent sur la **couleur projetée** au jour cible. "
        "0 = exclure."
    )

    quotas: dict[str, dict[str, int]] = {}
    header_cols = st.columns([2] + [1] * len(colors))
    header_cols[0].markdown("**Statut**")
    for index, color in enumerate(colors, start=1):
        header_cols[index].markdown(f"**{color}**")

    for status_index, status in enumerate(statuses):
        row_cols = st.columns([2] + [1] * len(colors))
        row_cols[0].write(status)
        quotas[status] = {}
        for color_index, color in enumerate(colors):
            max_available = available.get(status, {}).get(color, 0)
            with row_cols[color_index + 1]:
                quotas[status][color] = int(
                    st.number_input(
                        f"{status} / {color}",
                        min_value=0,
                        max_value=max(max_available, 0),
                        value=min(default_quota, max_available) if max_available else 0,
                        step=10,
                        key=f"{key_prefix}_quota_{status_index}_{color_index}",
                        label_visibility="collapsed",
                        help=f"Disponible : {max_available:,}",
                    )
                )

    total_quota = sum(
        color_quota for color_map in quotas.values() for color_quota in color_map.values()
    )
    st.info(f"Total demandé : **{total_quota:,}** contacts")
    return quotas


def _render_forecast_pivot(title: str, pivot_df: pd.DataFrame) -> None:
    st.markdown(f"**{title}**")
    if pivot_df is None or pivot_df.empty:
        st.info("Aucune donnée.")
        return
    display = pivot_df.copy()
    color_cols = [c for c in ALL_COLORS if c in display.columns]
    if color_cols:
        display = display.reindex(columns=color_cols + ["Total"], fill_value=0)
    st.dataframe(display, use_container_width=True)


def _get_forecast_working_df() -> tuple[pd.DataFrame | None, dict[str, int] | None]:
    """Applique le fichier d'exclusion enregistré sur le recyclage chargé."""
    raw = st.session_state.get("forecast_df_raw")
    if raw is None:
        return None, None
    exclude_tels = st.session_state.get("forecast_exclusion_tels") or set()
    filtered, stats = forecast.apply_tel_exclusion(raw, exclude_tels)
    return filtered, stats


def _render_forecast_main(
    df: pd.DataFrame,
    *,
    target_offset: int,
    sort_priority: str,
    forecast_quotas: dict[str, dict[str, int]] | None,
    generate_btn: bool,
    exclusion_stats: dict[str, int] | None = None,
) -> None:
    snapshot = forecast.forecast_snapshot(df, offsets=forecast.WEEK_OFFSETS)

    st.subheader("Prévisionnel couleurs — semaine")
    caption = (
        f"**{snapshot['total_rows']:,}** fiches analysées · "
        "projection J+1 à J+7 (sans nouvel appel)."
    )
    if exclusion_stats and exclusion_stats.get("removed", 0) > 0:
        caption += (
            f" · **{exclusion_stats['removed']:,}** TEL exclus "
            f"(fichier d'exclusion : {exclusion_stats.get('exclusion_size', 0):,} TEL)"
        )
    st.caption(caption)

    today_global = snapshot["today"]["global"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Red aujourd'hui", f"{today_global.get('Red', 0):,}")
    c2.metric("Orange aujourd'hui", f"{today_global.get('Orange', 0):,}")
    c3.metric("Blue aujourd'hui", f"{today_global.get('Blue', 0):,}")
    c4.metric("Green aujourd'hui", f"{today_global.get('Green', 0):,}")

    tab_today, tab_week, tab_reds, tab_day, tab_detail = st.tabs(
        ["Aujourd'hui", "Vue semaine", "Rouges par jours", "Détail par jour", "Vieillissement"]
    )

    with tab_today:
        _render_forecast_pivot("Répartition statut × couleur", snapshot["today"]["by_status"])
        red_today = snapshot.get("red_days_today")
        if red_today is not None and not red_today.empty:
            st.markdown("**Rouges par jours depuis dernier contact**")
            st.dataframe(red_today, hide_index=True, use_container_width=True)
            with st.expander("Détail par statut"):
                red_by_status = snapshot.get("red_days_by_status_today")
                if red_by_status is not None and not red_by_status.empty:
                    st.dataframe(red_by_status, hide_index=True, use_container_width=True)

    with tab_week:
        week_df = snapshot.get("week_timeline")
        if week_df is None or week_df.empty:
            st.info("Aucune donnée.")
        else:
            st.markdown("**Évolution des couleurs sur 7 jours**")
            st.dataframe(week_df, hide_index=True, use_container_width=True)

            st.markdown("**Orange par jour**")
            orange_chart = week_df.set_index("Jour")[["Orange", "Δ Orange vs auj."]]
            st.dataframe(orange_chart, use_container_width=True)

            st.markdown("**Transitions cumulées par jour**")
            for offset in forecast.WEEK_OFFSETS:
                block = snapshot["offsets"][offset]
                transitions = block["transitions_total"]
                if transitions.empty:
                    continue
                with st.expander(f"{block['label']} · {block['date']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Depuis aujourd'hui**")
                        st.dataframe(transitions, hide_index=True, use_container_width=True)
                    with c2:
                        st.markdown("**Nouveaux ce jour**")
                        inc = block["transitions_incremental"]
                        if inc.empty:
                            st.info("Aucun nouveau changement.")
                        else:
                            st.dataframe(inc, hide_index=True, use_container_width=True)

    with tab_reds:
        st.markdown("**Rouges aujourd'hui — par jours depuis dernier contact (14 → 0)**")
        red_today = snapshot.get("red_days_today")
        if red_today is None or red_today.empty:
            st.info("Aucun rouge.")
        else:
            total_reds = int(red_today["Fiches"].sum())
            st.caption(f"**{total_reds:,}** rouges au total · seuil orange = 15 jours")
            st.dataframe(red_today, hide_index=True, use_container_width=True)

        st.markdown("**Évolution semaine — combien restent rouges par bucket de départ**")
        red_matrix = snapshot.get("red_days_week_matrix")
        if red_matrix is not None and not red_matrix.empty:
            st.dataframe(red_matrix, hide_index=True, use_container_width=True)
            st.caption(
                "Chaque ligne = fiches rouges à X jours aujourd'hui. "
                "Les colonnes J+N montrent combien sont encore rouges à ce jour-là."
            )

        st.divider()
        red_offset = st.selectbox(
            "Projection rouges pour le jour",
            options=[0, *forecast.WEEK_OFFSETS],
            format_func=lambda x: "Aujourd'hui" if x == 0 else forecast.forecast_offset_label(x),
            key="forecast_red_offset",
        )
        if red_offset == 0:
            red_proj = snapshot.get("red_days_today")
            red_proj_status = snapshot.get("red_days_by_status_today")
            title = "Rouges aujourd'hui"
        else:
            block = snapshot["offsets"][red_offset]
            red_proj = block.get("red_days")
            red_proj_status = block.get("red_days_by_status")
            title = f"Rouges encore présents · {block['label']} ({block['date']})"
        st.markdown(f"**{title}**")
        if red_proj is None or red_proj.empty:
            st.info("Aucun rouge à cette date.")
        else:
            st.dataframe(red_proj, hide_index=True, use_container_width=True)
            with st.expander("Par statut"):
                if red_proj_status is not None and not red_proj_status.empty:
                    st.dataframe(red_proj_status, hide_index=True, use_container_width=True)

    with tab_day:
        day_offset = st.selectbox(
            "Jour à afficher",
            options=forecast.WEEK_OFFSETS,
            format_func=lambda x: forecast.forecast_offset_label(x),
            key="forecast_day_offset",
        )
        block = snapshot["offsets"][day_offset]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Date", block["date"])
        m2.metric("Fiches stables", f"{block['stable_count']:,}")
        m3.metric("Changements cumulés", f"{block['changing_count']:,}")
        global_proj = block["global"]
        m4.metric(
            "Orange projetés",
            f"{global_proj.get('Orange', 0):,}",
            delta=f"{global_proj.get('Orange', 0) - today_global.get('Orange', 0):+,}",
        )

        st.markdown("**Répartition projetée (statut × couleur)**")
        _render_forecast_pivot("", block["by_status"])

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Transitions depuis aujourd'hui**")
            if block["transitions_total"].empty:
                st.info("Aucun changement.")
            else:
                st.dataframe(block["transitions_total"], hide_index=True, use_container_width=True)
        with c2:
            st.markdown("**Nouveaux changements ce jour**")
            if block["transitions_incremental"].empty:
                st.info("Aucun nouveau changement.")
            else:
                st.dataframe(
                    block["transitions_incremental"], hide_index=True, use_container_width=True
                )

        with st.expander("Transitions par statut"):
            if block["transitions_by_status"].empty:
                st.info("Aucune transition.")
            else:
                st.dataframe(
                    block["transitions_by_status"],
                    hide_index=True,
                    use_container_width=True,
                )

        red_day = block.get("red_days")
        if red_day is not None and not red_day.empty:
            st.markdown("**Rouges par jours contact (encore rouges à cette date)**")
            st.dataframe(red_day, hide_index=True, use_container_width=True)

    with tab_detail:
        detail_offset = st.selectbox(
            "Jour de projection pour le détail",
            options=forecast.WEEK_OFFSETS,
            format_func=lambda x: forecast.forecast_offset_label(x),
            key="forecast_detail_offset",
        )
        color_focus = st.selectbox(
            "Couleur actuelle",
            options=["Toutes", "Red", "Orange", "Blue", "Green"],
            key="forecast_detail_color",
        )
        detail_df = forecast.aging_detail(
            df,
            detail_offset,
            color_filter=None if color_focus == "Toutes" else color_focus,
        )
        if detail_df.empty:
            st.info("Aucune fiche pour ce filtre.")
        else:
            st.dataframe(detail_df, hide_index=True, use_container_width=True)
            st.caption(
                "Ex. un rouge à 10 jours → 11 jours demain reste rouge ; "
                "un rouge à 14 jours → 15 jours demain devient orange."
            )

    if forecast_quotas is not None:
        st.divider()
        st.subheader("Sélection export")
        st.caption(
            f"Jour cible : **{forecast.forecast_offset_label(target_offset)}**"
        )

    if generate_btn and forecast_quotas is not None:
        try:
            excel_bytes, selected_df, summary = forecast.export_forecast_selection(
                df,
                target_offset,
                status_color_quotas=forecast_quotas,
                sort_priority=sort_priority,
            )
            st.session_state["forecast_excel_bytes"] = excel_bytes
            if exclusion_stats:
                summary["exclusion"] = exclusion_stats
            st.session_state["forecast_summary"] = summary
            st.session_state["forecast_selected_preview"] = selected_df
            st.success(
                f"Export généré : **{summary['total_selected']:,}** fiches "
                f"({summary['offset_label']})."
            )
        except Exception as exc:
            st.error(str(exc))

    if st.session_state.get("forecast_summary"):
        summary = st.session_state["forecast_summary"]
        st.markdown("**Résumé de la sélection**")
        c1, c2 = st.columns(2)
        with c1:
            if summary.get("by_status"):
                st.dataframe(
                    pd.DataFrame(
                        {
                            "Statut": list(summary["by_status"].keys()),
                            "Fiches": list(summary["by_status"].values()),
                        }
                    ).sort_values("Fiches", ascending=False),
                    hide_index=True,
                    use_container_width=True,
                )
        with c2:
            if summary.get("by_color"):
                st.dataframe(
                    pd.DataFrame(
                        {
                            "Couleur projetée": list(summary["by_color"].keys()),
                            "Fiches": list(summary["by_color"].values()),
                        }
                    ).sort_values("Fiches", ascending=False),
                    hide_index=True,
                    use_container_width=True,
                )
        if summary.get("transitions_in_selection"):
            st.markdown("**Transitions dans la sélection**")
            st.dataframe(
                pd.DataFrame(
                    {
                        "Transition": list(summary["transitions_in_selection"].keys()),
                        "Fiches": list(summary["transitions_in_selection"].values()),
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )

    if st.session_state.get("forecast_selected_preview") is not None:
        with st.expander("Aperçu des fiches sélectionnées"):
            preview_cols = [
                c
                for c in [
                    "TEL",
                    "Status_Category",
                    "Color_Original",
                    "Color",
                    "Days_Original",
                    "Days_Since_Last_Call",
                    "Transition",
                ]
                if c in st.session_state["forecast_selected_preview"].columns
            ]
            st.dataframe(
                st.session_state["forecast_selected_preview"][preview_cols].head(200),
                hide_index=True,
                use_container_width=True,
            )


def _render_diagnostics(stats: dict) -> None:
    st.subheader("Diagnostic du traitement")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lignes DB", f"{stats.get('db_rows', 0):,}")
    c2.metric("Lignes historique", f"{stats.get('hist_rows', 0):,}")
    c3.metric("TEL communs", f"{stats.get('common_tels', 0):,}")
    c4.metric("Lignes finales", f"{stats.get('latest_rows', 0):,}")

    with st.expander("Détails techniques", expanded=stats.get("latest_rows", 0) == 0):
        st.write("Colonnes DB :", ", ".join(stats.get("db_columns", [])))
        st.write("Colonnes historique :", ", ".join(stats.get("hist_columns", [])))


def _render_store_stats(*, before: dict[str, Any] | None = None) -> None:
    stats = database.get_store_stats()
    backend = stats.get("backend", "—")
    st.caption(f"Stockage : **{backend}** — {stats.get('database_url_hint', '')}")
    c1, c2, c3, c4 = st.columns(4)

    def _delta(key: str) -> str | None:
        if not before:
            return None
        old = before.get(key)
        new = stats.get(key)
        if old is None or new is None or old == new:
            return None
        diff = int(new) - int(old)
        return f"{diff:+,}"

    c1.metric(
        "TEL base client",
        f"{stats.get('db_tels', 0):,}",
        delta=_delta("db_tels"),
        help="Nombre de TEL uniques en base. Inchangé si seuls des TEL existants sont mis à jour.",
    )
    c2.metric(
        "Lignes historique",
        f"{stats.get('hist_rows', 0):,}",
        delta=_delta("hist_rows"),
    )
    c3.metric(
        "Appels Onoff",
        f"{stats.get('onoff_rows', 0):,}",
        delta=_delta("onoff_rows"),
        help="Nombre total d'appels Onoff enregistrés.",
    )
    c4.metric(
        "Durées Onoff (TEL)",
        f"{stats.get('onoff_totals_rows', 0):,}",
        delta=_delta("onoff_totals_rows"),
        help="TEL avec une durée totale Onoff calculée.",
    )
    st.caption(f"Dernière MAJ : **{stats.get('last_update', '—')}**")
    if stats.get("db_tels", 0) < 5000:
        st.warning(
            "Base petite détectée. Pour un export complet fusionné (~20 000 lignes), "
            "réinitialisez avec la **DB master complète** et l'**historique master complet**, "
            "puis appliquez les fichiers du jour."
        )
    if stats.get("updates"):
        with st.expander("Historique des mises à jour"):
            st.dataframe(pd.DataFrame(stats["updates"]).iloc[::-1], hide_index=True)


def _render_merge_persistence_report(
    report: dict[str, Any],
    before_stats: dict[str, Any],
) -> None:
    """Résumé clair : ce qui a été enregistré sur la base persistante."""
    after_stats = report.get("store") or database.get_store_stats()
    db_path = after_stats.get("database_url_hint", "recyclage.db")

    st.success(
        f"**Enregistré sur la base persistante** — {db_path}\n\n"
        "Les fusions du jour sont sauvegardées dans SQLite. "
        "Demain, uploadez uniquement les nouveaux fichiers du jour."
    )

    details: list[dict[str, str]] = []

    if "db" in report:
        db_part = report["db"]
        tel_after = after_stats.get("db_tels", 0)
        tel_before = before_stats.get("db_tels", 0)
        details.append(
            {
                "Donnée": "Base client (TEL)",
                "Avant": f"{tel_before:,}",
                "Après": f"{tel_after:,}",
                "Action": (
                    f"{db_part.get('updated_tels', 0):,} TEL mis à jour · "
                    f"{db_part.get('added_tels', 0):,} ajoutés · "
                    f"{db_part.get('skipped_new_tels', 0):,} nouveaux ignorés"
                ),
            }
        )

    if "history" in report:
        h = report["history"]
        details.append(
            {
                "Donnée": "Historique",
                "Avant": f"{before_stats.get('hist_rows', 0):,}",
                "Après": f"{after_stats.get('hist_rows', 0):,}",
                "Action": f"+{h.get('rows_added', 0):,} lignes ajoutées",
            }
        )

    if "onoff" in report:
        o = report["onoff"]
        details.append(
            {
                "Donnée": "Onoff (appels)",
                "Avant": f"{before_stats.get('onoff_rows', 0):,}",
                "Après": f"{after_stats.get('onoff_rows', 0):,}",
                "Action": f"+{o.get('rows_added', 0):,} appels",
            }
        )
        details.append(
            {
                "Donnée": "Onoff (durées TEL)",
                "Avant": f"{before_stats.get('onoff_totals_rows', 0):,}",
                "Après": f"{after_stats.get('onoff_totals_rows', 0):,}",
                "Action": f"+{o.get('totals_added', 0):,} TEL avec durée",
            }
        )

    if details:
        st.dataframe(pd.DataFrame(details), hide_index=True, use_container_width=True)

    if report.get("db", {}).get("updated_tels", 0) == 0 and report.get("db", {}).get("daily_tels", 0) > 0:
        st.warning(
            "Aucun TEL mis à jour. Vérifiez que la base master contient bien vos clients "
            "(réinitialisez avec la DB master complète si besoin)."
        )
    elif report.get("db", {}).get("updated_tels", 0) and report.get("db", {}).get("added_tels", 0) == 0:
        st.info(
            "Le nombre total de TEL reste identique car les fiches du jour **mettent à jour** "
            "des clients déjà en base (pas de nouveaux TEL ajoutés). "
            "Cochez « Autoriser les nouveaux TEL » pour en ajouter."
        )

    st.markdown("**État actuel de la base**")
    _render_store_stats(before=before_stats)


def _clear_export_cache() -> None:
    st.session_state.pop("excel_bytes", None)
    st.session_state.pop("summary", None)


class _PersistedUpload(io.BytesIO):
    """UploadedFile-like buffer backed by session state bytes."""

    def __init__(self, name: str, data: bytes):
        super().__init__(data)
        self.name = name
        self.type = None


def _persist_multi_upload(widget_key: str, storage_key: str) -> None:
    uploaded = st.session_state.get(widget_key)
    if uploaded:
        st.session_state[storage_key] = [
            {"name": f.name, "data": f.getvalue()} for f in uploaded
        ]


def _load_persisted_uploads(storage_key: str) -> list[_PersistedUpload]:
    raw = st.session_state.get(storage_key) or []
    return [_PersistedUpload(item["name"], item["data"]) for item in raw]


def _clear_persisted_upload(storage_key: str, widget_key: str, *, bump_key: str | None = None) -> None:
    st.session_state.pop(storage_key, None)
    st.session_state.pop(widget_key, None)
    if bump_key:
        st.session_state[bump_key] = st.session_state.get(bump_key, 0) + 1


def _clear_all_daily_uploads() -> None:
    for storage_key, widget_base_key, bump_key in (
        ("persisted_daily_db", "uploader_daily_db", "uploader_daily_db_rev"),
        ("persisted_daily_hist", "uploader_daily_hist", "uploader_daily_hist_rev"),
        ("persisted_daily_onoff", "uploader_daily_onoff", "uploader_daily_onoff_rev"),
    ):
        st.session_state.pop(storage_key, None)
        widget_key = f"{widget_base_key}_{st.session_state.get(bump_key, 0)}"
        st.session_state.pop(widget_key, None)
        st.session_state[bump_key] = st.session_state.get(bump_key, 0) + 1


def _on_persist_daily_db() -> None:
    rev = st.session_state.get("uploader_daily_db_rev", 0)
    _persist_multi_upload(f"uploader_daily_db_{rev}", "persisted_daily_db")


def _on_persist_daily_hist() -> None:
    rev = st.session_state.get("uploader_daily_hist_rev", 0)
    _persist_multi_upload(f"uploader_daily_hist_{rev}", "persisted_daily_hist")


def _render_multi_file_slot(
    *,
    label: str,
    storage_key: str,
    widget_base_key: str,
    rev_key: str,
    clear_button_key: str,
    file_types: list[str],
    on_change,
    help_text: str,
) -> None:
    persisted = st.session_state.get(storage_key) or []
    if persisted:
        names = ", ".join(item["name"] for item in persisted)
        c1, c2 = st.columns([4, 1])
        c1.success(f"✓ {label} ({len(persisted)} fichier(s)) : {names}")
        if c2.button("✕", key=clear_button_key, help=f"Retirer {label.lower()}"):
            widget_key = f"{widget_base_key}_{st.session_state.get(rev_key, 0)}"
            _clear_persisted_upload(storage_key, widget_key, bump_key=rev_key)
            st.rerun()
        return

    widget_key = f"{widget_base_key}_{st.session_state.get(rev_key, 0)}"
    st.file_uploader(
        label,
        type=file_types,
        accept_multiple_files=True,
        key=widget_key,
        on_change=on_change,
        help=help_text,
    )
    _persist_multi_upload(widget_key, storage_key)


def _render_onoff_uploader() -> list[_PersistedUpload] | None:
    """Onoff: uploader always visible (multi-file), like the original working UX."""
    widget_key = f"uploader_daily_onoff_{st.session_state.get('uploader_daily_onoff_rev', 0)}"
    uploaded = st.file_uploader(
        "Onoff du jour (optionnel)",
        type=["xls", "xlsx", "xlsm", "csv"],
        accept_multiple_files=True,
        key=widget_key,
        help="Sélectionnez 1 ou 2 fichiers b2b — l'uploader reste visible.",
    )
    if uploaded:
        st.session_state["persisted_daily_onoff"] = [
            {"name": f.name, "data": f.getvalue()} for f in uploaded
        ]
        st.caption(f"✓ {len(uploaded)} fichier(s) Onoff : {', '.join(f.name for f in uploaded)}")
    elif st.session_state.get("persisted_daily_onoff"):
        names = ", ".join(item["name"] for item in st.session_state["persisted_daily_onoff"])
        st.caption(f"✓ Onoff mémorisé : {names}")

    if st.button("Effacer Onoff", key="clear_daily_onoff", use_container_width=True):
        _clear_persisted_upload(
            "persisted_daily_onoff",
            widget_key,
            bump_key="uploader_daily_onoff_rev",
        )
        st.rerun()

    files = _load_persisted_uploads("persisted_daily_onoff")
    return files or None


def _render_persisted_daily_uploads() -> tuple:
    """Data/histo: multi-file with confirmation banner. Onoff: always-visible uploader."""
    st.caption(
        "Data et Histo : sélectionnez un ou plusieurs fichiers. "
        "Onoff : uploader toujours visible (2 fichiers possibles)."
    )

    _render_multi_file_slot(
        label="Data du jour",
        storage_key="persisted_daily_db",
        widget_base_key="uploader_daily_db",
        rev_key="uploader_daily_db_rev",
        clear_button_key="clear_daily_db",
        file_types=["xls", "xlsx", "xlsm"],
        on_change=_on_persist_daily_db,
        help_text="Un ou plusieurs exports client du jour (STATUS par TEL).",
    )

    _render_multi_file_slot(
        label="Histo du jour",
        storage_key="persisted_daily_hist",
        widget_base_key="uploader_daily_hist",
        rev_key="uploader_daily_hist_rev",
        clear_button_key="clear_daily_hist",
        file_types=["xls", "xlsx", "xlsm", "csv"],
        on_change=_on_persist_daily_hist,
        help_text="Un ou plusieurs exports historique du jour.",
    )

    merge_daily_onoff = _render_onoff_uploader()

    allow_new_tels = st.checkbox(
        "Autoriser les nouveaux TEL (data du jour)",
        value=False,
        key="merge_allow_new_tels",
    )
    merge_and_export_btn = st.button(
        "Mettre à jour et générer l'export complet",
        type="primary",
        use_container_width=True,
    )

    merge_daily_db = _load_persisted_uploads("persisted_daily_db")
    merge_daily_hist = _load_persisted_uploads("persisted_daily_hist")
    return merge_daily_db, merge_daily_hist, merge_daily_onoff, allow_new_tels, merge_and_export_btn


def _run_export(
    *,
    db_file,
    hist_file,
    onoff_files,
    use_store: bool,
    selected_statuses,
    selected_colors,
    limit_enabled,
    limit_scope,
    max_rows,
    status_color_quotas,
    sort_priority,
    fichier_filter: list[str] | None = None,
    fichier_filter_mode: str = "include",
) -> None:
    with st.spinner("Traitement en cours…"):
        try:
            if use_store and database.store_exists():
                latest, stats = process_data(
                    df_db=database.load_db(),
                    df_hist=database.load_history(),
                    return_stats=True,
                )
                latest, onoff_stats = database.attach_store_onoff(latest)
                latest = processor.attach_repondeur_profiles(latest, database.load_history())
            else:
                if not db_file or not hist_file:
                    raise ValueError("Chargez la base client et l'historique.")
                latest, stats = process_data(db_file, hist_file, return_stats=True)
                hist_df = database._prepare_hist_frame(
                    database._read_import(hist_file, is_history=True)
                )
                latest = processor.attach_repondeur_profiles(latest, hist_df)
                onoff_stats = {}
                if onoff_files:
                    latest, onoff_stats = attach_onoff_durations(latest, onoff_files)

            rows_before = len(latest)
            if fichier_filter:
                latest = database.apply_fichier_filter(
                    latest,
                    fichier_filter,
                    mode=fichier_filter_mode,
                )
                if latest.empty:
                    raise ValueError(
                        "Aucune ligne après filtre FICHIER. Élargissez la sélection."
                    )

            if latest.empty:
                raise ValueError("Aucune donnée à exporter après traitement.")

            if sort_priority == "duration":
                if "Total_Duration_Seconds" not in latest.columns:
                    latest["Total_Duration_Seconds"] = 0
                    latest["Total_Duration"] = "00:00:00"
                matched_duration = int((latest["Total_Duration_Seconds"] > 0).sum())
                if matched_duration == 0:
                    st.warning(
                        "Priorité « durée d'appel » activée mais aucune durée Onoff trouvée. "
                        "Importez les fichiers Onoff ou initialisez la base avec des appels Onoff."
                    )

            export_max_rows = int(max_rows) if limit_enabled and limit_scope != "custom" else None
            export_limit_scope = limit_scope if limit_enabled else "per_status"
            export_quotas = status_color_quotas if limit_enabled and limit_scope == "custom" else None

            matching, filtered = prepare_export_data(
                latest,
                selected_statuses=selected_statuses,
                selected_colors=selected_colors,
                max_rows=export_max_rows,
                limit_scope=export_limit_scope,
                status_color_quotas=export_quotas,
                sort_priority=sort_priority,
            )
            excel_bytes = export_excel(
                latest,
                selected_statuses=selected_statuses,
                selected_colors=selected_colors,
                max_rows=export_max_rows,
                limit_scope=export_limit_scope,
                status_color_quotas=export_quotas,
                sort_priority=sort_priority,
            )

            st.session_state["excel_bytes"] = excel_bytes
            st.session_state["summary"] = {
                "total_processed": len(latest),
                "total_before_fichier_filter": rows_before if fichier_filter else len(latest),
                "total_matching": len(matching),
                "total_exported": len(filtered),
                "limit_enabled": limit_enabled,
                "max_rows": export_max_rows,
                "limit_scope": export_limit_scope,
                "sort_priority": sort_priority,
                "fichier_filter": fichier_filter or [],
                "fichier_filter_mode": fichier_filter_mode,
                "rows_removed_by_fichier_filter": (rows_before - len(latest)) if fichier_filter else 0,
                "status_color_quotas": export_quotas,
                "onoff_stats": onoff_stats,
                "by_status": filtered["Status_Category"].value_counts().to_dict(),
                "by_color": filtered["Color"].value_counts().to_dict(),
                "by_status_color": (
                    filtered.groupby(["Status_Category", "Color"])
                    .size()
                    .reset_index(name="Lignes")
                    .to_dict("records")
                ),
            }
            st.success("Export prêt.")
        except Exception as exc:
            st.error(f"Erreur : {exc}")
            st.session_state.pop("excel_bytes", None)
            st.session_state.pop("summary", None)


st.set_page_config(
    page_title="Lead & Connect Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_theme()

with st.sidebar:
    render_sidebar_brand()
    app_mode = render_navigation(default="overview")

    store_ready = database.store_exists()
    store_stats = database.get_store_stats() if store_ready else {}

    analytics_modes = {"overview", "data_client", "ventes", "dashboard"}
    if app_mode in analytics_modes:
        st.divider()
        data_source = render_global_data_source(
            store_exists=store_ready,
            store_stats=store_stats,
            key_prefix=app_mode,
        )
        use_store = data_source["use_store"]
        db_file = data_source["db_file"]
        hist_file = data_source["hist_file"]
    else:
        use_store = store_ready
        db_file = hist_file = None

    if app_mode == "overview":
        init_btn = daily_btn = generate = merge_all_btn = False
        export_full = export_limited = False
        init_db = init_hist = init_onoff = daily_db = daily_hist = daily_onoff = None
        onoff_files = None
        selected_statuses = selected_colors = []
        limit_enabled = False
        limit_scope = "per_status"
        max_rows = 500
        sort_priority = "oldest"
        stale_days = 60
        retry_days = 90
        vente_track_config = None
        fichier_filter = None
        data_client_filters = None

        st.divider()
        current_year = datetime.now().year
        overview_year = st.selectbox(
            "Année de référence (ventes)",
            options=list(range(current_year - 2, current_year + 2)),
            index=2,
            key="overview_year",
        )
        refresh_overview = st.button(
            "Actualiser la vue d'ensemble",
            type="primary",
            use_container_width=True,
            key="overview_refresh",
        )
        overview_config = {"year": overview_year, "refresh": refresh_overview}
        ventes_filters = None

    elif app_mode == "data_client":
        init_btn = daily_btn = generate = merge_all_btn = False
        export_full = export_limited = False
        init_db = init_hist = init_onoff = daily_db = daily_hist = daily_onoff = None
        onoff_files = None
        selected_statuses = selected_colors = []
        limit_enabled = False
        limit_scope = "per_status"
        max_rows = 500
        sort_priority = "oldest"
        stale_days = 60
        retry_days = 90
        vente_track_config = None
        fichier_filter = None
        overview_config = None
        ventes_filters = None

        st.divider()
        st.markdown("**FILTRES**")
        dc_colors = st.multiselect(
            "Couleur",
            options=data_client_dashboard.COLOR_DISPLAY_ORDER,
            default=data_client_dashboard.COLOR_DISPLAY_ORDER,
            key="dc_colors",
        )
        dc_statuses = st.multiselect(
            "Statut (optionnel)",
            options=data_client_dashboard.STATUS_DISPLAY_ORDER,
            default=[],
            key="dc_statuses",
            help="Filtre les statuts affichés. Laissez vide pour tous les statuts des couleurs sélectionnées.",
        )
        current_year = datetime.now().year
        dc_year = st.selectbox(
            "Année",
            options=list(range(current_year - 2, current_year + 2)),
            index=2,
            key="dc_year",
        )
        month_labels = ["Tous les mois"] + [
            datetime(2000, m, 1).strftime("%B").capitalize() for m in range(1, 13)
        ]
        month_values = [None, *range(1, 13)]
        dc_month_idx = st.selectbox(
            "Mois",
            options=range(len(month_labels)),
            format_func=lambda i: month_labels[i],
            key="dc_month",
        )
        dc_month_value = month_values[dc_month_idx]

        refresh_data_client = st.button(
            "APPLIQUER LES FILTRES",
            type="primary",
            use_container_width=True,
            key="dc_apply_filters",
        )
        export_data_client = st.button(
            "Exporter",
            use_container_width=True,
            key="dc_export_btn",
        )

        if refresh_data_client or "dc_applied" not in st.session_state:
            st.session_state["dc_applied"] = {
                "year": dc_year,
                "month": dc_month_value,
                "colors": dc_colors or None,
                "statuses": dc_statuses or None,
            }

        applied = st.session_state["dc_applied"]
        data_client_filters = {
            "year": applied["year"],
            "month": applied["month"],
            "colors": applied["colors"],
            "statuses": applied["statuses"],
            "refresh": refresh_data_client or "data_client_metrics" not in st.session_state,
            "export": export_data_client,
        }

    elif app_mode == "ventes":
        init_btn = daily_btn = generate = merge_all_btn = False
        export_full = export_limited = False
        init_db = init_hist = init_onoff = daily_db = daily_hist = daily_onoff = None
        onoff_files = None
        selected_statuses = selected_colors = []
        limit_enabled = False
        limit_scope = "per_status"
        max_rows = 500
        sort_priority = "oldest"
        stale_days = 60
        retry_days = 90
        fichier_filter = None
        overview_config = None
        data_client_filters = None

        st.divider()
        st.markdown("**Période & filtres**")
        current_year = datetime.now().year
        v_year = st.selectbox(
            "Année ventes",
            options=list(range(current_year - 2, current_year + 2)),
            index=2,
            key="ventes_year",
        )
        month_labels = ["Tous les mois"] + [
            datetime(2000, m, 1).strftime("%B").capitalize() for m in range(1, 13)
        ]
        month_values = [None, *range(1, 13)]
        v_month_idx = st.selectbox(
            "Mois",
            options=range(len(month_labels)),
            format_func=lambda i: month_labels[i],
            key="ventes_month",
        )
        v_month = month_values[v_month_idx]
        v_prior_colors = st.multiselect(
            "Couleur avant vente",
            options=data_client_dashboard.COLOR_DISPLAY_ORDER,
            default=[],
            key="ventes_prior_colors",
            help="Filtre sur la couleur du contact avant la vente.",
        )
        v_prior_statuses = st.multiselect(
            "Statut avant vente",
            options=data_client_dashboard.STATUS_DISPLAY_ORDER,
            default=[],
            key="ventes_prior_statuses",
            help="Filtre sur le statut du contact avant la vente.",
        )

        st.divider()
        st.markdown("**Suivi quotidien**")
        baseline_mode = st.radio(
            "Source baseline",
            options=["store_snapshot+upload", "store_snapshot", "recyclage_upload", "client_upload"],
            format_func=lambda x: {
                "store_snapshot+upload": "Snapshot base + uploads",
                "store_snapshot": "Snapshot base seul",
                "recyclage_upload": "Export recyclage uploadé",
                "client_upload": "Fichiers client uploadés",
            }[x],
            index=0,
            key="ventes_vt_baseline_mode",
        )
        baseline_recyclage_file = None
        baseline_client_files: list = []
        if baseline_mode in ("recyclage_upload", "store_snapshot+upload"):
            baseline_recyclage_file = st.file_uploader(
                "Export recyclage (baseline)",
                type=["xls", "xlsx", "xlsm"],
                key="ventes_vt_baseline_recyclage",
            )
        if baseline_mode in ("client_upload", "store_snapshot+upload"):
            baseline_client_files = st.file_uploader(
                "Fichiers client baseline",
                type=["xls", "xlsx", "xlsm"],
                accept_multiple_files=True,
                key="ventes_vt_baseline_client",
            ) or []
        daily_vente_files = st.file_uploader(
            "Exports ventes du jour",
            type=["xls", "xlsx", "xlsm"],
            accept_multiple_files=True,
            key="ventes_vt_daily",
        ) or []
        save_vente_history = st.checkbox(
            "Enregistrer dans l'historique",
            value=True,
            key="ventes_vt_save_history",
        )
        capture_baseline_btn = st.button(
            "Capturer baseline",
            use_container_width=True,
            key="ventes_vt_capture",
        )
        analyze_ventes_btn = st.button(
            "Analyser ventes du jour",
            use_container_width=True,
            key="ventes_vt_analyze",
        )
        vente_track_config = {
            "baseline_mode": baseline_mode,
            "baseline_recyclage_file": baseline_recyclage_file,
            "baseline_client_files": baseline_client_files,
            "daily_vente_files": daily_vente_files,
            "save_to_history": save_vente_history,
            "analyze_btn": analyze_ventes_btn,
            "capture_baseline_btn": capture_baseline_btn,
        }
        ventes_filters = {
            "year": v_year,
            "month": v_month,
            "prior_colors": v_prior_colors or None,
            "prior_statuses": v_prior_statuses or None,
        }

    elif app_mode == "database":
        store_ready = database.store_exists()
        merge_master_db = merge_master_hist = merge_master_onoff = None
        init_db = init_hist = init_onoff = None
        init_btn = False
        daily_btn = False
        full_merge_btn = False

        if store_ready:
            store_stats = database.get_store_stats()
            st.header("Mise à jour du jour")
            st.caption(
                "La **base master est enregistrée**. Uploadez vos fichiers du jour "
                "(plusieurs fichiers possibles par zone)."
            )
            st.success(
                f"Base enregistrée : **{store_stats.get('db_tels', 0):,}** TEL · "
                f"**{store_stats.get('hist_rows', 0):,}** lignes historique"
            )

            (
                merge_daily_db,
                merge_daily_hist,
                merge_daily_onoff,
                allow_new_tels,
                merge_and_export_btn,
            ) = _render_persisted_daily_uploads()
        else:
            st.header("Initialisation de la base")
            st.caption(
                "Importez **une seule fois** la DB master et l'historique master. "
                "Ensuite, seuls les fichiers du jour seront nécessaires chaque matin."
            )
            init_db = st.file_uploader(
                "DB master",
                type=["xls", "xlsx", "xlsm"],
                key="init_db_main",
            )
            init_hist = st.file_uploader(
                "Historique master",
                type=["xls", "xlsx", "xlsm", "csv"],
                key="init_hist_main",
            )
            init_onoff = st.file_uploader(
                "Onoff master (optionnel)",
                type=["xls", "xlsx", "xlsm", "csv"],
                accept_multiple_files=True,
                key="init_onoff_main",
                help="Totals Onoff + logs b2b historiques.",
            )
            init_btn = st.button(
                "Enregistrer la base master",
                type="primary",
                use_container_width=True,
            )
            merge_daily_db = merge_daily_hist = merge_daily_onoff = None
            merge_and_export_btn = False
            allow_new_tels = False

        if not store_ready:
            allow_new_tels = st.checkbox(
                "Autoriser les nouveaux TEL (data du jour)",
                value=False,
                key="merge_allow_new_tels_init",
            )

        st.markdown("**Filtre FICHIER (avant export final)**")
        fichier_filter_enabled = st.checkbox(
            "Activer le filtre FICHIER sur l'export",
            value=False,
            key="db_fichier_filter_enabled",
            help="Les FICHIER sélectionnés/exclus sont retirés du fichier Excel final.",
            on_change=_clear_export_cache,
        )
        fichier_filter_mode = "include"
        selected_fichiers: list[str] = []
        if fichier_filter_enabled:
            fichier_filter_mode = st.radio(
                "Mode filtre",
                options=["include", "exclude"],
                format_func=lambda x: {
                    "include": "Conserver uniquement ces FICHIER",
                    "exclude": "Exclure ces FICHIER de l'export",
                }[x],
                key="db_fichier_filter_mode",
                on_change=_clear_export_cache,
            )
            if store_ready:
                fichier_options = database.get_fichier_values()
            elif init_db is not None:
                try:
                    fichier_options = database.get_fichier_values_from_db_source(init_db)
                except Exception:
                    fichier_options = []
            else:
                fichier_options = []
            if fichier_options:
                default_values = fichier_options if fichier_filter_mode == "exclude" else []
                selected_fichiers = st.multiselect(
                    "Valeurs FICHIER",
                    options=fichier_options,
                    default=default_values,
                    key="db_fichier_values",
                    on_change=_clear_export_cache,
                )
                if fichier_filter_mode == "include":
                    st.caption(
                        f"{len(fichier_options)} fichiers disponibles · "
                        f"{len(selected_fichiers)} conservés dans l'export."
                    )
                else:
                    st.caption(
                        f"{len(fichier_options)} fichiers disponibles · "
                        f"{len(selected_fichiers)} exclus de l'export."
                    )
            else:
                st.info("Initialisez la base pour lister les valeurs FICHIER.")
        if fichier_filter_enabled and not selected_fichiers:
            fichier_filter = [] if fichier_filter_mode == "include" else None
        elif fichier_filter_enabled:
            fichier_filter = selected_fichiers
        else:
            fichier_filter = None

        if not store_ready:
            merge_and_export_btn = False

        with st.expander("Options avancées"):
            if store_ready:
                st.markdown("**Réinitialiser la base master**")
                init_db = st.file_uploader(
                    "DB master", type=["xls", "xlsx", "xlsm"], key="init_db"
                )
                init_hist = st.file_uploader(
                    "Historique master", type=["xls", "xlsx", "xlsm", "csv"], key="init_hist"
                )
                init_onoff = st.file_uploader(
                    "Onoff master (optionnel)",
                    type=["xls", "xlsx", "xlsm", "csv"],
                    accept_multiple_files=True,
                    key="init_onoff",
                )
                init_btn = st.button(
                    "Réinitialiser la base master",
                    use_container_width=True,
                )

                st.divider()
                st.markdown("**MAJ du jour sans export**")
                st.caption("Utilisez les uploaders principaux ci-dessus pour la MAJ quotidienne.")
                daily_btn = False

                st.divider()
                st.markdown("**Fusion complète master + jour** (remplace tout)")
                merge_master_db = st.file_uploader(
                    "DB master", type=["xls", "xlsx", "xlsm"], key="merge_master_db"
                )
                merge_master_hist = st.file_uploader(
                    "Historique master", type=["xls", "xlsx", "xlsm", "csv"], key="merge_master_hist"
                )
                merge_master_onoff = st.file_uploader(
                    "Onoff master (optionnel)",
                    type=["xls", "xlsx", "xlsm", "csv"],
                    accept_multiple_files=True,
                    key="merge_master_onoff",
                )
                full_merge_btn = st.button(
                    "Fusion complète master + jour + export",
                    use_container_width=True,
                )
            else:
                daily_db = daily_hist = daily_onoff = None
                full_merge_btn = False

        merge_all_btn = False
        db_export_full_btn = False
        db_export_limited_btn = False
        if database.store_exists():
            st.divider()
            st.header("Ré-exporter depuis la base")
            db_export_full_btn = st.button(
                "Générer l'export complet",
                use_container_width=True,
                key="db_export_full",
            )
            with st.expander("Export limité (suivi dev)"):
                all_status_labels = sorted(DEFAULT_STATUS_MAPPING.values())
                selected_statuses = st.multiselect(
                    "Statuts", options=all_status_labels, default=all_status_labels, key="db_export_statuses"
                )
                selected_colors = st.multiselect(
                    "Couleurs", options=ALL_COLORS, default=ALL_COLORS, key="db_export_colors"
                )
                limit_enabled = st.checkbox("Limiter", value=True, key="db_limit_enabled")
                limit_scope = st.radio(
                    "Mode",
                    options=["per_status", "total_balanced", "total_oldest", "custom"],
                    format_func=lambda x: {
                        "per_status": "Par statut",
                        "total_balanced": "Total réparti",
                        "total_oldest": "Total global",
                        "custom": "Quotas statut × couleur",
                    }[x],
                    index=3,
                    disabled=not limit_enabled,
                    key="db_limit_scope",
                )
                max_rows = st.number_input(
                    "Max", min_value=1, value=500, step=50,
                    disabled=not limit_enabled or limit_scope == "custom",
                    key="db_max_rows",
                )
                sort_priority = st.radio(
                    "Priorité", options=["oldest", "duration"],
                    format_func=lambda x: SORT_PRIORITY_LABELS[x], index=1, key="db_sort_priority",
                )
                db_export_limited_btn = st.button("Export limité", key="db_export_limited")
        else:
            selected_statuses = selected_colors = []
            limit_enabled = False
            limit_scope = "per_status"
            max_rows = 500
            sort_priority = "oldest"
            fichier_filter = None
            fichier_filter_enabled = False
            fichier_filter_mode = "include"

        db_file = hist_file = onoff_files = None
        use_store = True
        export_full = db_export_full_btn
        export_limited = db_export_limited_btn
        generate = export_full or export_limited
        merge_all_btn = merge_and_export_btn
        stale_days = 60
        retry_days = 90
        refresh_dashboard = False
        data_client_filters = None
        ventes_filters = None
    elif app_mode == "dashboard":
        init_btn = daily_btn = generate = merge_all_btn = False
        export_full = export_limited = False
        init_db = init_hist = init_onoff = daily_db = daily_hist = daily_onoff = None
        onoff_files = None
        selected_statuses = selected_colors = []
        limit_enabled = False
        limit_scope = "per_status"
        max_rows = 500
        status_color_quotas = None
        sort_priority = "oldest"
        vente_track_config = None
        data_client_filters = None
        overview_config = None
        ventes_filters = None

        st.divider()
        st.markdown("**Paramètres**")
        stale_days = st.slider("Seuil contacts obsolètes (jours)", 30, 120, 60, 5)
        retry_days = st.slider("Fenêtre relances (jours)", 7, 180, 90, 7)

        st.divider()
        st.markdown("**Suivi ventes quotidien**")
        st.caption(
            "Baseline = statut **avant** les appels. Capturer avant la MAJ du jour, "
            "ou uploader l'export recyclage du matin."
        )
        baseline_mode = st.radio(
            "Source baseline",
            options=["store_snapshot+upload", "store_snapshot", "recyclage_upload", "client_upload"],
            format_func=lambda x: {
                "store_snapshot+upload": "Snapshot base + uploads",
                "store_snapshot": "Snapshot base seul",
                "recyclage_upload": "Export recyclage uploadé",
                "client_upload": "Fichiers client uploadés",
            }[x],
            index=0,
            key="vt_baseline_mode",
        )
        baseline_recyclage_file = None
        baseline_client_files: list = []
        if baseline_mode in ("recyclage_upload", "store_snapshot+upload"):
            baseline_recyclage_file = st.file_uploader(
                "Export recyclage (Recyclage_Data_Client.xlsx)",
                type=["xls", "xlsx", "xlsm"],
                key="vt_baseline_recyclage",
            )
        if baseline_mode in ("client_upload", "store_snapshot+upload"):
            baseline_client_files = st.file_uploader(
                "Fichiers client baseline (Book2, data-client…)",
                type=["xls", "xlsx", "xlsm"],
                accept_multiple_files=True,
                key="vt_baseline_client",
            ) or []
        daily_vente_files = st.file_uploader(
            "Exports ventes du jour (export_data_client)",
            type=["xls", "xlsx", "xlsm"],
            accept_multiple_files=True,
            key="vt_daily_ventes",
        ) or []
        save_vente_history = st.checkbox(
            "Enregistrer dans l'historique",
            value=True,
            key="vt_save_history",
        )
        capture_baseline_btn = st.button(
            "Capturer baseline (base actuelle)",
            use_container_width=True,
            key="vt_capture_baseline",
        )
        analyze_ventes_btn = st.button(
            "Analyser les ventes",
            type="primary",
            use_container_width=True,
            key="vt_analyze",
        )
        refresh_dashboard = st.button("Actualiser indicateurs", use_container_width=True)

        vente_track_config = {
            "baseline_mode": baseline_mode,
            "baseline_recyclage_file": baseline_recyclage_file,
            "baseline_client_files": baseline_client_files,
            "daily_vente_files": daily_vente_files,
            "save_to_history": save_vente_history,
            "analyze_btn": analyze_ventes_btn,
            "capture_baseline_btn": capture_baseline_btn,
        }
        data_client_filters = None
    elif app_mode == "forecast":
        init_btn = daily_btn = generate = merge_all_btn = False
        export_full = export_limited = False
        init_db = init_hist = init_onoff = daily_db = daily_hist = daily_onoff = None
        stale_days = 60
        retry_days = 90
        refresh_dashboard = False
        use_store = False
        db_file = hist_file = onoff_files = None
        selected_statuses = selected_colors = []
        limit_enabled = False
        limit_scope = "custom"
        max_rows = 500
        fichier_filter = None
        fichier_filter_enabled = False
        fichier_filter_mode = "include"
        vente_track_config = None
        ventes_filters = None

        st.header("Fichier recyclage")
        st.caption(
            "Uploadez un export Recyclage_Data_Client (.xlsx) pour projeter "
            "les couleurs de demain et après-demain."
        )
        forecast_file = st.file_uploader(
            "Recyclage_Data_Client",
            type=["xls", "xlsx", "xlsm"],
            key="forecast_upload",
        )
        if forecast_file is not None:
            st.session_state["forecast_upload_bytes"] = {
                "name": forecast_file.name,
                "data": forecast_file.getvalue(),
            }
            try:
                st.session_state["forecast_df_raw"] = forecast.load_recyclage_export(
                    io.BytesIO(forecast_file.getvalue())
                )
                st.session_state.pop("forecast_df", None)
                st.session_state.pop("forecast_excel_bytes", None)
                st.session_state.pop("forecast_summary", None)
                st.session_state.pop("forecast_selected_preview", None)
            except Exception as exc:
                st.session_state.pop("forecast_df_raw", None)
                st.error(f"Erreur lecture : {exc}")
        forecast_upload = st.session_state.get("forecast_upload_bytes")
        if forecast_upload:
            st.success(f"Fichier chargé : **{forecast_upload['name']}**")
            if st.button("Changer de fichier", key="forecast_clear_upload"):
                st.session_state.pop("forecast_upload_bytes", None)
                st.session_state.pop("forecast_df_raw", None)
                st.session_state.pop("forecast_df", None)
                st.session_state.pop("forecast_excel_bytes", None)
                st.session_state.pop("forecast_summary", None)
                st.session_state.pop("forecast_selected_preview", None)
                st.rerun()

        st.divider()
        st.header("Fichier d'exclusion")
        st.caption(
            "Enregistrez un fichier (ex. Book1) : les TEL qu'il contient seront "
            "retirés du prévisionnel et de l'export final."
        )
        exclusion_file = st.file_uploader(
            "Book1 / sélection déjà traitée",
            type=["xls", "xlsx", "xlsm", "csv"],
            key="forecast_exclusion_upload",
        )
        if exclusion_file is not None:
            try:
                st.session_state["forecast_exclusion_bytes"] = {
                    "name": exclusion_file.name,
                    "data": exclusion_file.getvalue(),
                }
                st.session_state["forecast_exclusion_tels"] = forecast.load_exclusion_tels(
                    io.BytesIO(exclusion_file.getvalue())
                )
                st.session_state.pop("forecast_excel_bytes", None)
                st.session_state.pop("forecast_summary", None)
                st.session_state.pop("forecast_selected_preview", None)
            except Exception as exc:
                st.session_state.pop("forecast_exclusion_tels", None)
                st.error(f"Erreur lecture exclusion : {exc}")

        exclusion_upload = st.session_state.get("forecast_exclusion_bytes")
        exclusion_tels = st.session_state.get("forecast_exclusion_tels") or set()
        if exclusion_upload:
            st.success(
                f"Exclusion enregistrée : **{exclusion_upload['name']}** "
                f"({len(exclusion_tels):,} TEL)"
            )
            if st.button("Retirer le fichier d'exclusion", key="forecast_clear_exclusion"):
                st.session_state.pop("forecast_exclusion_bytes", None)
                st.session_state.pop("forecast_exclusion_tels", None)
                st.session_state.pop("forecast_excel_bytes", None)
                st.session_state.pop("forecast_summary", None)
                st.session_state.pop("forecast_selected_preview", None)
                st.rerun()

        st.divider()
        st.header("Jour cible export")
        target_offset = st.radio(
            "Sélectionner pour l'export final",
            options=forecast.WEEK_OFFSETS,
            format_func=lambda x: forecast.forecast_offset_label(x),
            index=0,
            key="forecast_target_offset",
        )

        st.subheader("Priorité de sélection")
        sort_priority = st.radio(
            "Trier les fiches retenues par",
            options=["oldest", "duration"],
            format_func=lambda x: SORT_PRIORITY_LABELS[x],
            index=0,
            key="forecast_sort_priority",
        )

        forecast_quotas = None
        forecast_df, exclusion_stats = _get_forecast_working_df()
        if forecast_upload and forecast_df is not None and not forecast_df.empty:
            if exclusion_stats and exclusion_stats.get("removed", 0) > 0:
                st.info(
                    f"**{exclusion_stats['removed']:,}** fiches retirées "
                    f"({exclusion_stats.get('matched_in_source', 0):,} TEL trouvés "
                    f"sur {exclusion_stats.get('exclusion_size', 0):,} dans le fichier d'exclusion)."
                )
            available = forecast.available_projected_counts(forecast_df, target_offset)
            forecast_quotas = _render_forecast_quotas(
                available,
                default_quota=0,
                key_prefix=f"fc_{target_offset}",
            )
        elif forecast_upload and (forecast_df is None or (hasattr(forecast_df, "empty") and forecast_df.empty)):
            raw = st.session_state.get("forecast_df_raw")
            if raw is not None and not raw.empty and exclusion_stats and exclusion_stats.get("removed"):
                st.warning(
                    "Toutes les fiches ont été exclues par le fichier Book1. "
                    "Retirez ou changez le fichier d'exclusion."
                )
            else:
                st.warning("Aucune fiche trouvée dans le fichier.")

        st.divider()
        generate_forecast_btn = st.button(
            "Générer l'export prévisionnel",
            type="primary",
            use_container_width=True,
            key="forecast_generate_btn",
        )
        data_client_filters = None
        ventes_filters = None
    else:
        init_btn = daily_btn = merge_all_btn = False
        export_full = export_limited = False
        init_db = init_hist = init_onoff = daily_db = daily_hist = daily_onoff = None
        stale_days = 60
        retry_days = 90
        refresh_dashboard = False
        sort_priority = "oldest"

        store_ready = database.store_exists()
        use_store = st.checkbox(
            "Utiliser la base enregistrée",
            value=store_ready,
            disabled=not store_ready,
        )

        st.header("Fichiers")
        if use_store:
            store_stats = database.get_store_stats()
            st.info(
                f"Export depuis la base enregistrée ({store_stats.get('backend', 'SQL')})."
            )
            db_file = hist_file = onoff_files = None
        else:
            db_file = st.file_uploader("Base client (DB)", type=["xls", "xlsx", "xlsm"])
            hist_file = st.file_uploader(
                "Historique", type=["xls", "xlsx", "xlsm", "csv"]
            )
            onoff_files = st.file_uploader(
                "Exports Onoff (durées)",
                type=["xls", "xlsx", "xlsm", "csv"],
                accept_multiple_files=True,
            )

        st.divider()
        st.header("Filtres d'export")
        all_status_labels = sorted(DEFAULT_STATUS_MAPPING.values())
        selected_statuses = st.multiselect(
            "Statuts à inclure", options=all_status_labels, default=all_status_labels
        )
        selected_colors = st.multiselect(
            "Couleurs à inclure", options=ALL_COLORS, default=ALL_COLORS
        )

        st.divider()
        st.header("Volume d'export")
        limit_enabled = st.checkbox("Limiter le nombre de contacts", value=False)
        limit_scope = st.radio(
            "Mode de limite",
            options=["per_status", "total_balanced", "total_oldest", "custom"],
            format_func=lambda x: {
                "per_status": "Par statut (N max par feuille)",
                "total_balanced": "Total réparti",
                "total_oldest": "Total global (plus anciens)",
                "custom": "Personnalisé (quota statut × couleur)",
            }[x],
            index=3,
            disabled=not limit_enabled,
        )
        max_rows = st.number_input(
            "Nombre maximum",
            min_value=1,
            value=500,
            step=50,
            disabled=not limit_enabled or limit_scope == "custom",
        )

        st.subheader("Priorité de sélection")
        sort_priority = st.radio(
            "Trier les fiches retenues par",
            options=["oldest", "duration"],
            format_func=lambda x: SORT_PRIORITY_LABELS[x],
            index=1,
            help=(
                "Exemple : quota 300 en Green → les 300 fiches Vertes avec "
                "les plus grandes durées d'appel Onoff."
            ),
        )

        st.divider()
        generate = st.button("Générer l'export", type="primary", use_container_width=True)
        data_client_filters = None


if app_mode == "overview":
    can_render_overview = (use_store and database.store_exists()) or (
        not use_store and db_file is not None and hist_file is not None
    )
    if can_render_overview:
        _render_overview_dashboard(
            use_store=use_store,
            db_file=db_file,
            hist_file=hist_file,
            year=overview_config["year"] if overview_config else datetime.now().year,
            refresh=bool(overview_config and overview_config.get("refresh")),
        )
    else:
        render_section_header(
            "Vue d'ensemble",
            "Hub analytics — KPIs Data Client, performance, ventes et base persistante",
        )
        st.info(
            "Activez la **base persistante** ou uploadez la base client et l'historique "
            "dans la barre latérale."
        )

elif app_mode == "ventes":
    render_section_header(
        "Ventes",
        "Analyse des parcours — statut et couleur avant vente, matrice origine, suivi quotidien",
        badge=f"Année {ventes_filters['year']}" if ventes_filters else None,
    )
    can_render_ventes = (use_store and database.store_exists()) or (
        not use_store and db_file is not None and hist_file is not None
    )
    if can_render_ventes and ventes_filters is not None:
        _render_ventes_analytics(
            use_store=use_store,
            db_file=db_file,
            hist_file=hist_file,
            year=ventes_filters["year"],
            month=ventes_filters["month"],
            prior_colors=ventes_filters["prior_colors"],
            prior_statuses=ventes_filters["prior_statuses"],
            vente_track_config=vente_track_config,
        )
    else:
        st.info(
            "Activez la base persistante ou uploadez DB + historique dans la barre latérale."
        )

elif app_mode == "data_client":
    render_section_header(
        "Data Client",
        "KPIs, répartition couleur/statut, chaîne exploitables",
        badge=f"Année {data_client_filters['year']}" if data_client_filters else None,
    )
    can_render_dc = (use_store and database.store_exists()) or (
        not use_store and db_file is not None and hist_file is not None
    )
    if can_render_dc and data_client_filters is not None:
        _render_data_client_dashboard(
            use_store=use_store,
            db_file=db_file,
            hist_file=hist_file,
            year=data_client_filters["year"],
            month=data_client_filters["month"],
            colors=data_client_filters["colors"],
            statuses=data_client_filters.get("statuses"),
            refresh=bool(data_client_filters.get("refresh")),
        )
    elif not can_render_dc:
        st.info(
            "Chargez la base et l'historique dans la barre latérale, "
            "ou activez la base persistante, puis cliquez **APPLIQUER LES FILTRES**."
        )

else:
    section_titles = {
        "dashboard": ("Performance", "Conversion, parcours statuts, obsolètes, ventes"),
        "forecast": ("Prévisionnel", "Projection J+1 à J+7, quotas et export"),
        "export": ("Export recyclage", "Sélection par statut, couleur et quotas"),
        "database": ("Base de données", "Fusion quotidienne et persistance SQLite"),
    }
    if app_mode in section_titles:
        title, subtitle = section_titles[app_mode]
        render_section_header(title, subtitle)

    show_legend = app_mode in ("export", "dashboard", "database")
    if show_legend:
        col_info, col_legend = st.columns([2, 1])
        with col_legend:
            with st.expander("Légende couleurs"):
                st.markdown(
                    """
                    - **Green** — plus de 60 jours depuis le dernier contact
                    - **Blue** — entre 39 et 60 jours
                    - **Orange** — entre 15 et 38 jours
                    - **Red** — moins de 15 jours
                    """
                )
    else:
        col_info = st.container()

    with col_info:
        if app_mode == "dashboard":
            if database.store_exists():
                _render_store_stats()
            can_render_dashboard = (use_store and database.store_exists()) or (
                not use_store and db_file is not None and hist_file is not None
            )
            if can_render_dashboard:
                _render_performance_dashboard(
                    use_store=use_store,
                    db_file=db_file,
                    hist_file=hist_file,
                    stale_days=stale_days,
                    retry_days=retry_days,
                    vente_track_config=vente_track_config,
                    refresh=bool(refresh_dashboard),
                )
            else:
                st.info(
                    "Chargez la base et l'historique dans la barre latérale, "
                    "ou activez la base enregistrée."
                )

        elif app_mode == "database":
            if database.store_exists():
                if not merge_all_btn and not daily_btn:
                    st.subheader("État de la base")
                    _render_store_stats()
            else:
                st.warning(
                    "Base non initialisée. Uploadez la **DB master** et l'**historique master** "
                    "dans la barre latérale (une seule fois)."
                )

            if init_btn:
                if not init_db or not init_hist:
                    st.error("DB master et historique master sont obligatoires.")
                else:
                    try:
                        init_label = (
                            "réinitialisation master"
                            if database.store_exists()
                            else "initialisation master"
                        )
                        stats = database.initialize_store(
                            init_db, init_hist, init_onoff or None, label=init_label
                        )
                        st.success(
                            f"Base master enregistrée : {stats['db_tels']:,} TEL · "
                            f"{stats['hist_rows']:,} lignes historique · "
                            f"{stats['onoff_rows']:,} appels Onoff."
                        )
                        _render_store_stats()
                    except Exception as exc:
                        st.error(f"Erreur initialisation : {exc}")

            if merge_all_btn:
                if fichier_filter == [] and fichier_filter_mode == "include":
                    st.error("Filtre FICHIER : sélectionnez au moins une valeur à conserver.")
                elif not database.store_exists():
                    st.error(
                        "Base non initialisée. Enregistrez d'abord la DB et l'historique master "
                        "(une seule fois)."
                    )
                elif not merge_daily_db or not merge_daily_hist:
                    missing = []
                    if not merge_daily_db:
                        missing.append("Data du jour")
                    if not merge_daily_hist:
                        missing.append("Histo du jour")
                    st.error(
                        f"Fichiers manquants : **{', '.join(missing)}**. "
                        "Uploadez chaque fichier — un bandeau vert confirme la mémorisation."
                    )
                else:
                    try:
                        before_stats = database.get_store_stats()
                        with st.spinner("Mise à jour du jour en cours…"):
                            report = database.apply_daily_update(
                                daily_db=merge_daily_db,
                                daily_hist=merge_daily_hist,
                                daily_onoff=merge_daily_onoff or None,
                                allow_new_tels=allow_new_tels,
                                label="fusion quotidienne",
                            )
                        st.subheader("Fusion enregistrée")
                        _render_merge_persistence_report(report, before_stats)

                        preview_rows = database.process_merged_store()[0]
                        st.info(
                            f"Données fusionnées : **{len(preview_rows):,}** lignes exportables."
                        )

                        with st.spinner("Génération de l'export complet coloré…"):
                            excel_bytes, summary = database.export_full_recyclage(
                                fichier_filter=fichier_filter,
                                fichier_filter_mode=fichier_filter_mode,
                            )
                        st.session_state["excel_bytes"] = excel_bytes
                        st.session_state["summary"] = summary
                        st.success(
                            f"Export complet prêt : **{summary['total_exported']:,}** lignes "
                            f"sur {len(summary.get('by_status', {}))} feuilles."
                            + (
                                f" ({summary.get('rows_removed_by_fichier_filter', 0):,} lignes "
                                f"retirées par filtre FICHIER)"
                                if summary.get("rows_removed_by_fichier_filter")
                                else ""
                            )
                        )
                        _clear_all_daily_uploads()
                    except Exception as exc:
                        st.error(f"Erreur mise à jour : {exc}")

            elif full_merge_btn:
                if not merge_master_db or not merge_master_hist:
                    st.error("DB master et historique master sont obligatoires pour la fusion complète.")
                elif not merge_daily_db and not merge_daily_hist and not merge_daily_onoff:
                    st.error("Uploadez au moins un fichier du jour (Data, Histo ou Onoff).")
                elif fichier_filter == [] and fichier_filter_mode == "include":
                    st.error("Filtre FICHIER : sélectionnez au moins une valeur à conserver.")
                else:
                    try:
                        with st.spinner("Fusion master + jour en cours…"):
                            report = database.merge_master_and_daily(
                                master_db=merge_master_db,
                                master_hist=merge_master_hist,
                                master_onoff=merge_master_onoff or None,
                                daily_db=merge_daily_db,
                                daily_hist=merge_daily_hist,
                                daily_onoff=merge_daily_onoff or None,
                                allow_new_tels=allow_new_tels,
                            )
                        m = report["master"]
                        st.success(
                            f"Master chargé : {m['db_tels']:,} TEL · {m['hist_rows']:,} lignes historique."
                        )
                        d = report["daily"]
                        if "db" in d:
                            st.write(
                                f"DB fusionnée : {d['db']['updated_tels']:,} TEL mis à jour · "
                                f"{d['db'].get('added_tels', 0):,} ajoutés."
                            )
                        if "history" in d:
                            st.write(f"Historique : +{d['history']['rows_added']:,} lignes.")
                        if "onoff" in report:
                            o = report["onoff"]
                            st.write(
                                f"Onoff fusionné : {o.get('onoff_rows', 0):,} appels · "
                                f"{o.get('onoff_totals_rows', 0):,} TEL (totaux)."
                            )
                        _render_store_stats()
                        with st.spinner("Génération de l'export complet coloré…"):
                            excel_bytes, summary = database.export_full_recyclage(
                                fichier_filter=fichier_filter,
                                fichier_filter_mode=fichier_filter_mode,
                            )
                        st.session_state["excel_bytes"] = excel_bytes
                        st.session_state["summary"] = summary
                        st.success(
                            f"Export complet prêt : **{summary['total_exported']:,}** lignes."
                        )
                    except Exception as exc:
                        st.error(f"Erreur fusion : {exc}")

            if daily_btn:
                if not database.store_exists():
                    st.error("Initialisez d'abord la base master.")
                elif not daily_db and not daily_hist and not daily_onoff:
                    st.error("Importez au moins un fichier du jour.")
                else:
                    try:
                        before_stats = database.get_store_stats()
                        report = database.apply_daily_update(
                            daily_db=daily_db,
                            daily_hist=daily_hist,
                            daily_onoff=daily_onoff or None,
                            allow_new_tels=allow_new_tels,
                        )
                        st.subheader("Fusion enregistrée")
                        _render_merge_persistence_report(report, before_stats)
                        preview_rows = database.process_merged_store()[0]
                        st.info(
                            f"Base fusionnée prête : **{len(preview_rows):,}** lignes exportables. "
                            "Utilisez **Générer l'export complet** pour obtenir le fichier type (15).xlsx."
                        )
                    except Exception as exc:
                        st.error(f"Erreur mise à jour : {exc}")

            if database.store_exists():
                status_color_quotas = None
                if (
                    export_limited
                    and limit_enabled
                    and limit_scope == "custom"
                    and selected_statuses
                    and selected_colors
                ):
                    status_color_quotas = _render_custom_quotas(
                        selected_statuses,
                        selected_colors,
                        sort_priority=sort_priority,
                    )

                if generate:
                    if export_full:
                        if fichier_filter == [] and fichier_filter_mode == "include":
                            st.error("Filtre FICHIER : sélectionnez au moins une valeur à conserver.")
                        else:
                            try:
                                with st.spinner("Génération export complet…"):
                                    excel_bytes, summary = database.export_full_recyclage(
                                        fichier_filter=fichier_filter,
                                        fichier_filter_mode=fichier_filter_mode,
                                    )
                                st.session_state["excel_bytes"] = excel_bytes
                                st.session_state["summary"] = {
                                    **summary,
                                    "limit_enabled": False,
                                    "limit_scope": "per_status",
                                    "sort_priority": "oldest",
                                }
                                st.success(f"Export complet : {summary['total_exported']:,} lignes.")
                            except Exception as exc:
                                st.error(f"Erreur export : {exc}")
                    elif not selected_statuses or not selected_colors:
                        st.warning("Sélectionnez au moins un statut et une couleur.")
                    elif (
                        limit_enabled
                        and limit_scope == "custom"
                        and sum(
                            q for colors in (status_color_quotas or {}).values() for q in colors.values()
                        )
                        <= 0
                    ):
                        st.warning("Définissez au moins un quota > 0.")
                    elif fichier_filter == [] and fichier_filter_mode == "include":
                        st.error("Filtre FICHIER : sélectionnez au moins une valeur à conserver.")
                    else:
                        _run_export(
                            db_file=None,
                            hist_file=None,
                            onoff_files=None,
                            use_store=True,
                            selected_statuses=selected_statuses,
                            selected_colors=selected_colors,
                            limit_enabled=limit_enabled,
                            limit_scope=limit_scope,
                            max_rows=max_rows,
                            status_color_quotas=status_color_quotas,
                            sort_priority=sort_priority,
                            fichier_filter=fichier_filter,
                            fichier_filter_mode=fichier_filter_mode,
                        )

        elif app_mode == "forecast":
            forecast_df, exclusion_stats = _get_forecast_working_df()
            if not st.session_state.get("forecast_upload_bytes"):
                st.info(
                    "Uploadez un fichier **Recyclage_Data_Client.xlsx** dans la barre latérale "
                    "pour voir les projections demain / après-demain et générer une sélection."
                )
            elif forecast_df is None or forecast_df.empty:
                st.warning("Le fichier ne contient aucune fiche exploitable.")
            else:
                _render_forecast_main(
                    forecast_df,
                    target_offset=target_offset,
                    sort_priority=sort_priority,
                    forecast_quotas=forecast_quotas,
                    generate_btn=generate_forecast_btn,
                    exclusion_stats=exclusion_stats,
                )

        else:
            status_color_quotas = None
            if limit_enabled and limit_scope == "custom" and selected_statuses and selected_colors:
                status_color_quotas = _render_custom_quotas(
                    selected_statuses,
                    selected_colors,
                    sort_priority=sort_priority,
                )

            if database.store_exists() and use_store:
                _render_store_stats()

            if generate:
                if not use_store and (not db_file or not hist_file):
                    st.warning("Chargez la base client et l'historique, ou activez la base enregistrée.")
                elif not selected_statuses or not selected_colors:
                    st.warning("Sélectionnez au moins un statut et une couleur.")
                elif (
                    limit_enabled
                    and limit_scope == "custom"
                    and sum(
                        q for colors in (status_color_quotas or {}).values() for q in colors.values()
                    )
                    <= 0
                ):
                    st.warning("Définissez au moins un quota > 0.")
                else:
                    _run_export(
                        db_file=db_file,
                        hist_file=hist_file,
                        onoff_files=onoff_files,
                        use_store=use_store,
                        selected_statuses=selected_statuses,
                        selected_colors=selected_colors,
                        limit_enabled=limit_enabled,
                        limit_scope=limit_scope,
                        max_rows=max_rows,
                        status_color_quotas=status_color_quotas,
                        sort_priority=sort_priority,
                    )
            elif not database.store_exists() and not use_store:
                st.info("Initialisez la base dans l'onglet **Base de données**, ou uploadez les fichiers manuellement.")

    if "summary" in st.session_state and app_mode in ("export", "database"):
        summary = st.session_state["summary"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("TEL traités", f"{summary['total_processed']:,}")
        m2.metric("Correspondances", f"{summary['total_matching']:,}")
        m3.metric("Lignes exportées", f"{summary['total_exported']:,}")
        m4.metric("Feuilles", len(summary["by_status"]))

        if summary.get("onoff_stats"):
            onoff = summary["onoff_stats"]
            st.caption(
                f"Durées Onoff : {onoff.get('onoff_tels_matched', 0):,} TEL durée totale · "
                f"{onoff.get('onoff_last_call_matched', 0):,} dernier appel · "
                f"{onoff.get('onoff_tels_without_duration', 0):,} sans durée · "
                f"total {_format_duration_label(onoff.get('onoff_total_duration_seconds', 0))}"
            )

        if summary.get("fichier_filter"):
            mode_label = "exclus" if summary.get("fichier_filter_mode") == "exclude" else "conservés"
            st.caption(
                f"Filtre FICHIER ({mode_label}) : {', '.join(summary['fichier_filter'])}"
                + (
                    f" · {summary.get('rows_removed_by_fichier_filter', 0):,} lignes retirées"
                    if summary.get("rows_removed_by_fichier_filter")
                    else ""
                )
            )

        _render_export_summary(summary)

    if "excel_bytes" in st.session_state and app_mode in ("export", "database"):
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        st.download_button(
            label="Télécharger Recyclage_Data_Client.xlsx",
            data=st.session_state["excel_bytes"],
            file_name=f"Recyclage_Data_Client_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

    if "forecast_excel_bytes" in st.session_state and app_mode == "forecast":
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        offset = st.session_state.get("forecast_summary", {}).get("offset_days", 1)
        st.download_button(
            label="Télécharger export prévisionnel",
            data=st.session_state["forecast_excel_bytes"],
            file_name=f"Recyclage_Previsionnel_J{offset}_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,

    )

if "data_client_excel_bytes" in st.session_state and app_mode == "data_client":
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    st.download_button(
        label="Télécharger tableau de bord Data Client",
        data=st.session_state["data_client_excel_bytes"],
        file_name=f"Data_Client_Dashboard_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )

if "ventes_excel_bytes" in st.session_state and app_mode == "ventes":
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    st.download_button(
        label="Télécharger rapport ventes",
        data=st.session_state["ventes_excel_bytes"],
        file_name=f"Ventes_Analytics_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
