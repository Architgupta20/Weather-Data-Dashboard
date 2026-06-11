"""Streamlit UI for the Real-Time Weather Intelligence Platform."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import APP_NAME, APP_TAGLINE, DEMO_MODE, LIVE_MODE, OPENWEATHER_API_KEY, TRACKED_CITIES
from data_loader import (
    latest_event_timestamp,
    latest_reading_per_city,
    load_aggregates,
    load_alerts,
    load_events,
    with_event_time,
)
from forecasting import generate_forecast
from live_fetcher import fetch_city_forecast
from live_pipeline import refresh_live_data
from weather_metrics import enrich_weather_frame

FORECAST_METHODS = {
    "auto": "Auto (Prophet → ETS → linear)",
    "prophet": "Prophet",
    "exponential_smoothing": "Exponential smoothing (statsmodels)",
    "linear_trend": "Linear trend",
}

FORECAST_METRICS = {
    "temperature": "Temperature (°C)",
    "humidity": "Humidity (%)",
    "wind_speed": "Wind speed (m/s)",
    "heat_index": "Heat index / feels like (°C)",
}

STALE_AFTER_SECONDS = 120
DEFAULT_CITIES = sorted(TRACKED_CITIES)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
)


PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0B0C0F",
    plot_bgcolor="#12141A",
    font=dict(color="#B8BEC8", size=12),
)


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background-color: #0B0C0F; }
        .main .block-container { padding-top: 1.25rem; padding-bottom: 2rem; max-width: 100%; }
        h1 { color: #C5CAD3 !important; font-weight: 700 !important; font-size: 1.55rem !important; line-height: 1.3 !important; margin-bottom: 0.15rem !important; }
        h2, h3, h4, h5 { color: #C5CAD3 !important; font-weight: 600 !important; }
        p, label, span { color: #A8AEB8; }
        [data-testid="stTabs"] { margin-top: 0.5rem; }
        [data-testid="stMetric"] {
            background: #15171C;
            border: 1px solid #252830;
            border-radius: 8px;
            padding: 0.6rem 0.75rem;
        }
        [data-testid="stMetricValue"] { color: #D0D5DD !important; font-size: 1.35rem !important; }
        [data-testid="stDataFrame"] { border: 1px solid #252830; border-radius: 8px; }
        div[data-baseweb="tab"] { color: #9AA1AD; }
        div[data-baseweb="tab-highlight"] { background-color: #6B8CAE !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _apply_plotly_theme(fig: go.Figure) -> go.Figure:
    fig.update_layout(**PLOTLY_LAYOUT)
    return fig


def filter_by_cities(df: pd.DataFrame, cities: list[str], city_col: str = "city") -> pd.DataFrame:
    if df.empty or not cities or city_col not in df.columns:
        return df
    return df[df[city_col].isin(cities)].copy()


def format_event_time(ts: datetime | None) -> str:
    if ts is None:
        return "—"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def pipeline_status(events: pd.DataFrame, stale_after_seconds: int) -> tuple[str, str]:
    if LIVE_MODE:
        if not OPENWEATHER_API_KEY:
            return "Live mode — API key missing", "error"
        if events.empty:
            return "Live mode — fetch failed", "error"
        return "Live (OpenWeather API)", "success"
    if DEMO_MODE:
        return "Demo mode (sample data)", "success"
    if events.empty:
        return "No data", "error"
    latest = latest_event_timestamp(events)
    if latest is None:
        return "Unknown", "warning"
    age = datetime.now(timezone.utc) - latest.astimezone(timezone.utc)
    if age > timedelta(seconds=stale_after_seconds):
        return f"Stale ({int(age.total_seconds())}s old)", "warning"
    return "Healthy", "success"


def render_sidebar_refresh() -> tuple[int, bool]:
    st.sidebar.markdown("##### Refresh")
    refresh_seconds = st.sidebar.slider("Interval (sec)", 15, 120, 15, label_visibility="visible")
    auto_refresh = st.sidebar.toggle("Auto-refresh", value=True)
    if st.sidebar.button("Refresh now", use_container_width=True, type="primary"):
        st.rerun()
    return refresh_seconds, auto_refresh


def render_world_map(snapshot: pd.DataFrame) -> None:
    mapped = snapshot.dropna(subset=["lat", "lon"])
    if mapped.empty:
        st.caption("Map unavailable for the current city selection.")
        return

    hover = mapped.apply(
        lambda r: (
            f"<b>{r['city']}</b><br>"
            f"Temp: {r['temperature']:.1f}°C<br>"
            f"Feels like: {r.get('heat_index', r['temperature']):.1f}°C<br>"
            f"Humidity: {r['humidity']:.0f}%<br>"
            f"{r.get('weather_condition', '')}"
        ),
        axis=1,
    )

    fig = go.Figure(
        data=go.Scattergeo(
            lon=mapped["lon"],
            lat=mapped["lat"],
            text=mapped["city"],
            hovertext=hover,
            hoverinfo="text",
            mode="markers",
            marker=dict(
                size=16,
                color=mapped["heat_index"] if "heat_index" in mapped.columns else mapped["temperature"],
                colorscale="YlOrRd",
                cmin=mapped["heat_index"].min() if "heat_index" in mapped.columns else None,
                cmax=mapped["heat_index"].max() if "heat_index" in mapped.columns else None,
                colorbar=dict(title="Heat index (°C)"),
                line=dict(width=1.5, color="white"),
            ),
        )
    )
    fig.update_geos(
        projection_type="natural earth",
        showland=True,
        landcolor="#2A2E36",
        showcountries=True,
        countrycolor="#3A3F4A",
        showocean=True,
        oceancolor="#12141A",
        bgcolor="#0B0C0F",
    )
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0))
    _apply_plotly_theme(fig)
    st.plotly_chart(fig, use_container_width=True)


def _format_delta(value: float | None) -> str:
    if value is None:
        return "—"
    if value > 0:
        return f"+{value:.1f}"
    if value < 0:
        return f"{value:.1f}"
    return "0.0"


def _build_live_comparison_table(snapshot: pd.DataFrame) -> pd.DataFrame:
    """Compare current readings to the previous refresh (per city)."""
    prev = st.session_state.get("prev_city_snapshot", pd.DataFrame())
    prev_by_city = (
        prev.set_index("city")
        if not prev.empty and "city" in prev.columns
        else pd.DataFrame()
    )

    rows: list[dict] = []
    clean = snapshot.dropna(subset=["city"]).copy()
    clean = clean[clean["city"].astype(str).str.strip() != ""]
    for _, row in clean.iterrows():
        city = row["city"]
        cur_temp = float(row["temperature"])
        cur_hum = float(row["humidity"])
        cur_wind = float(row["wind_speed"])
        updated = pd.to_datetime(row["event_time"], utc=True).strftime("%H:%M:%S UTC")

        if city in prev_by_city.index:
            prev_temp = float(prev_by_city.loc[city, "temperature"])
            prev_hum = float(prev_by_city.loc[city, "humidity"])
            prev_wind = float(prev_by_city.loc[city, "wind_speed"])
        else:
            prev_temp = prev_hum = prev_wind = None

        rows.append(
            {
                "City": city,
                "Prev temp (°C)": round(prev_temp, 1) if prev_temp is not None else "—",
                "Now temp (°C)": round(cur_temp, 1),
                "Δ Temp": _format_delta(None if prev_temp is None else cur_temp - prev_temp),
                "Prev humidity (%)": round(prev_hum, 1) if prev_hum is not None else "—",
                "Now humidity (%)": round(cur_hum, 1),
                "Δ Humidity": _format_delta(None if prev_hum is None else cur_hum - prev_hum),
                "Prev wind (m/s)": round(prev_wind, 1) if prev_wind is not None else "—",
                "Now wind (m/s)": round(cur_wind, 1),
                "Δ Wind": _format_delta(None if prev_wind is None else cur_wind - prev_wind),
                "Updated": updated,
                "Conditions": row.get("weather_condition", ""),
            }
        )

    st.session_state.prev_city_snapshot = clean[
        ["city", "temperature", "humidity", "wind_speed", "event_time"]
    ].copy()
    return pd.DataFrame(rows).reset_index(drop=True)


def _table_height(row_count: int) -> int:
    """Fit dataframe height to rows — avoids empty row at the bottom."""
    if row_count <= 0:
        return 120
    return 38 + row_count * 35


def render_dashboard_tab(
    snapshot: pd.DataFrame,
    recent: pd.DataFrame,
    available_cities: list[str],
) -> None:
    if snapshot.empty:
        st.warning("No data for the selected cities.")
        return

    snapshot = enrich_weather_frame(snapshot)
    recent = enrich_weather_frame(recent)
    hottest = snapshot.loc[snapshot["temperature"].idxmax()]
    refresh_sec = st.session_state.get("refresh_seconds", 15)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Cities", len(snapshot))
    k2.metric("Avg temp", f"{snapshot['temperature'].mean():.1f}°C")
    k3.metric("Hottest", f"{hottest['city']}", f"{hottest['temperature']:.1f}°C")
    k4.metric("Avg humidity", f"{snapshot['humidity'].mean():.0f}%")

    st.markdown("##### Live city readings")
    st.caption(
        f"Auto-refreshes every **{refresh_sec}s**. "
        "**Prev** = value at last refresh · **Now** = current value · **Δ** = change since last refresh."
    )

    filter_col, reset_col = st.columns([5, 1])
    with filter_col:
        st.multiselect(
            "Filter cities",
            options=available_cities,
            key="table_city_filter",
            label_visibility="collapsed",
            placeholder="Filter cities…",
        )
    with reset_col:
        if st.button("All", use_container_width=True, help="Show all cities"):
            st.session_state.table_city_filter = available_cities
            st.rerun()

    selected = st.session_state.get("table_city_filter", available_cities)
    snapshot = snapshot[snapshot["city"].isin(selected)] if selected else snapshot.iloc[0:0]

    if snapshot.empty:
        st.info("Select at least one city to display readings.")
        return

    comparison = _build_live_comparison_table(snapshot)
    st.dataframe(
        comparison,
        use_container_width=True,
        hide_index=True,
        height=_table_height(len(comparison)),
    )

    st.markdown("##### Temperature ranking")
    bar_fig = px.bar(
        snapshot.sort_values("temperature", ascending=True),
        x="temperature",
        y="city",
        orientation="h",
        color="temperature",
        color_continuous_scale="Tealgrn",
    )
    bar_fig.update_layout(showlegend=False, height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="", xaxis_title="°C")
    _apply_plotly_theme(bar_fig)
    st.plotly_chart(bar_fig, use_container_width=True)

    with st.expander("Recent history", expanded=False):
        if recent.empty:
            st.caption("No rows for this filter.")
        else:
            hist = recent.tail(20).copy()
            if "event_time" in hist.columns:
                hist["Updated"] = pd.to_datetime(hist["event_time"], utc=True).dt.strftime("%H:%M:%S UTC")
            st.dataframe(
                hist[
                    [c for c in ["city", "Updated", "temperature", "humidity", "wind_speed", "weather_condition"] if c in hist.columns]
                ],
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("##### Global map")
    render_world_map(snapshot)


def render_alerts_tab(alerts: pd.DataFrame) -> None:
    if alerts.empty:
        st.info("No alerts in this session yet. Threshold rules (heat wave, high wind, etc.) will appear here.")
        return

    filtered = alerts.copy()
    high_count = int((filtered["severity"] == "high").sum()) if "severity" in filtered.columns else 0
    a1, a2, a3 = st.columns(3)
    a1.metric("Total alerts", len(filtered))
    a2.metric("High severity", high_count)
    a3.metric("Cities affected", filtered["city"].nunique() if "city" in filtered.columns else 0)

    with st.expander("Filters", expanded=False):
        severities = sorted(filtered["severity"].dropna().unique()) if "severity" in filtered.columns else []
        f1, f2 = st.columns(2)
        with f1:
            severity_filter = st.multiselect("Severity", options=severities, default=severities, key="alert_severity_filter")
        with f2:
            last_24h_only = st.checkbox("Last 24 hours only", value=False, key="alert_24h")
        if severity_filter and "severity" in filtered.columns:
            filtered = filtered[filtered["severity"].isin(severity_filter)]
        if last_24h_only and "detected_at" in filtered.columns:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            filtered = filtered[filtered["detected_at"] >= cutoff]

    display = filtered.copy()
    if "detected_at" in display.columns:
        display["detected_at"] = pd.to_datetime(display["detected_at"], utc=True).dt.strftime("%Y-%m-%d %H:%M UTC")
    show_cols = [c for c in ["detected_at", "city", "severity", "alert_type", "metric", "value", "message"] if c in display.columns]
    st.dataframe(display[show_cols], use_container_width=True, hide_index=True)

    if not filtered.empty and "severity" in filtered.columns and filtered["city"].nunique() > 0:
        hist = px.histogram(filtered, x="city", color="severity", barmode="group")
        hist.update_layout(height=280, margin=dict(t=10, b=10))
        _apply_plotly_theme(hist)
        st.plotly_chart(hist, use_container_width=True)


@st.cache_data(ttl=60, show_spinner="Generating forecast...")
def cached_forecast(
    events: pd.DataFrame,
    city: str,
    metric: str,
    periods: int,
    method_preference: str,
    data_version: str,
):
    return generate_forecast(
        events,
        city,
        metric,
        periods,
        method_preference=method_preference,
    )


def _merge_alert_history(new_alerts: pd.DataFrame) -> pd.DataFrame:
    """Keep alerts visible for the session even when the latest fetch detects none."""
    stored = st.session_state.get("alert_history", pd.DataFrame())
    if new_alerts.empty:
        return stored.copy()

    combined = pd.concat([stored, new_alerts], ignore_index=True)
    dedupe_cols = [c for c in ["city", "metric", "alert_type"] if c in combined.columns]
    if dedupe_cols:
        combined = combined.drop_duplicates(subset=dedupe_cols, keep="last")
    if "detected_at" in combined.columns:
        combined = combined.sort_values("detected_at", ascending=False)
    elif "timestamp" in combined.columns:
        combined = combined.sort_values("timestamp", ascending=False)
    st.session_state.alert_history = combined.reset_index(drop=True)
    return st.session_state.alert_history.copy()


def get_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if LIVE_MODE:
        history = st.session_state.get("event_history", pd.DataFrame())
        events, aggregates, new_alerts, updated_history = refresh_live_data(history)
        st.session_state.event_history = updated_history
        st.session_state.live_aggregates = aggregates
        alerts = _merge_alert_history(new_alerts)
        return events, aggregates, alerts
    return load_events(), load_aggregates(), load_alerts()


def render_live_forecast_tab(city: str, metric: str, periods: int) -> None:
    if metric == "heat_index":
        st.warning("Live API forecast supports temperature, humidity, and wind speed. Select one of those.")
        return
    try:
        forecast = fetch_city_forecast(city, metric, steps=periods)
    except Exception as exc:
        st.error(f"Could not fetch live forecast: {exc}")
        return

    f1, f2 = st.columns(2)
    f1.metric("Next value", round(float(forecast.iloc[0]["yhat"]), 2))
    f2.metric("Model", "OpenWeather API")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=forecast["ds"],
            y=forecast["yhat"],
            mode="lines+markers",
            name="Forecast",
            line=dict(color="#ff7f0e"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["ds"],
            y=forecast["yhat_upper"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["ds"],
            y=forecast["yhat_lower"],
            mode="lines",
            fill="tonexty",
            name="Band",
            line=dict(width=0),
            fillcolor="rgba(255, 127, 14, 0.2)",
        )
    )
    fig.update_layout(
        title=f"{city} — {FORECAST_METRICS.get(metric, metric)} (live)",
        xaxis_title="Time (UTC)",
        yaxis_title=FORECAST_METRICS.get(metric, metric),
        hovermode="x unified",
    )
    _apply_plotly_theme(fig)
    st.plotly_chart(fig, use_container_width=True)


def render_forecast_tab(events: pd.DataFrame) -> None:
    events = enrich_weather_frame(events)
    cities = sorted(events["city"].dropna().unique().tolist()) if not events.empty else DEFAULT_CITIES
    metric_options = [m for m in FORECAST_METRICS if events.empty or m in events.columns]

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            city = st.selectbox("City", options=cities, key="forecast_city")
        with c2:
            metric = st.selectbox(
                "Metric",
                options=metric_options,
                format_func=lambda m: FORECAST_METRICS[m],
                key="forecast_metric",
            )
        with c3:
            if LIVE_MODE:
                st.text_input("Model", value="OpenWeather API", disabled=True, key="forecast_model_live")
                method_pref = "auto"
            else:
                method_pref = st.selectbox(
                    "Model",
                    options=list(FORECAST_METHODS.keys()),
                    format_func=lambda k: FORECAST_METHODS[k],
                    key="forecast_method",
                )
        with c4:
            periods = st.slider("Steps ahead", min_value=3, max_value=12, value=6, key="forecast_periods")

    if LIVE_MODE:
        render_live_forecast_tab(city, metric, periods)
        return

    if events.empty:
        st.warning("No historical data available yet. Run the pipeline to collect events.")
        return

    latest_ts = latest_event_timestamp(events)
    version_key = f"{len(events)}_{latest_ts}_{method_pref}"
    result = cached_forecast(events, city, metric, periods, method_pref, version_key)

    if result.method == "none":
        st.warning(result.message)
        return

    m1, m2, m3 = st.columns(3)
    m1.caption("Model")
    m1.write(result.method.replace("_", " ").title())
    if result.forecast.empty:
        st.warning("Forecast could not be generated.")
        return

    next_value = float(result.forecast.iloc[0]["yhat"])
    m2.metric("Next forecast", round(next_value, 2))
    m3.metric("MAE / RMSE", f"{'—' if result.mae is None else round(result.mae, 2)} / {'—' if result.rmse is None else round(result.rmse, 2)}")

    fig = go.Figure()
    history = result.history.copy()
    forecast = result.forecast.copy()
    history["ds"] = pd.to_datetime(history["ds"], utc=True)
    forecast["ds"] = pd.to_datetime(forecast["ds"], utc=True)

    fig.add_trace(
        go.Scatter(
            x=history["ds"],
            y=history["y"],
            mode="lines+markers",
            name="Historical actual",
            line=dict(color="#1f77b4"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["ds"],
            y=forecast["yhat"],
            mode="lines+markers",
            name="Forecast",
            line=dict(color="#ff7f0e", dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["ds"],
            y=forecast["yhat_upper"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["ds"],
            y=forecast["yhat_lower"],
            mode="lines",
            fill="tonexty",
            name="Confidence band",
            line=dict(width=0),
            fillcolor="rgba(255, 127, 14, 0.2)",
        )
    )
    fig.update_layout(
        title=f"{city} — {metric} forecast",
        xaxis_title="Time (UTC)",
        yaxis_title=FORECAST_METRICS.get(metric, metric),
        hovermode="x unified",
    )
    _apply_plotly_theme(fig)
    st.plotly_chart(fig, use_container_width=True)

    if not result.holdout_actual.empty and not result.holdout_predicted.empty:
        with st.expander("Holdout validation", expanded=False):
            holdout_fig = go.Figure()
            holdout_fig.add_trace(
                go.Scatter(
                    x=result.holdout_actual["ds"],
                    y=result.holdout_actual["y"],
                    mode="lines+markers",
                    name="Actual (holdout)",
                )
            )
            holdout_fig.add_trace(
                go.Scatter(
                    x=result.holdout_predicted["ds"],
                    y=result.holdout_predicted["yhat"],
                    mode="lines+markers",
                    name="Predicted (holdout)",
                )
            )
            holdout_fig.update_layout(
                xaxis_title="Time (UTC)",
                yaxis_title=FORECAST_METRICS.get(metric, metric),
                height=300,
                margin=dict(t=10, b=10),
            )
            st.plotly_chart(holdout_fig, use_container_width=True)


def render_aggregates_tab(aggregates: pd.DataFrame) -> None:
    if aggregates.empty:
        msg = "Aggregates build up as live data collects (keep the tab open ~5 min)." if LIVE_MODE else "Start `consumer_spark.py` to populate aggregates."
        st.info(msg)
        return

    with st.container(border=True):
        g1, g2 = st.columns([2, 1])
        with g1:
            metric = st.selectbox(
                "Metric",
                options=[
                    ("avg_temperature", "Temperature (°C)"),
                    ("avg_humidity", "Humidity (%)"),
                    ("avg_wind_speed", "Wind speed (m/s)"),
                ],
                format_func=lambda x: x[1],
                key="aggregate_metric",
            )
        with g2:
            max_windows = st.slider("Windows", min_value=6, max_value=48, value=12, step=6)

    metric_col = metric[0]
    plot_df = aggregates.tail(max_windows).copy()

    if {"window_start", "city", metric_col}.issubset(plot_df.columns):
        line = px.line(plot_df, x="window_start", y=metric_col, color="city", markers=True)
        line.update_layout(height=320, margin=dict(t=10, b=10))
        _apply_plotly_theme(line)
        st.plotly_chart(line, use_container_width=True)

    with st.expander("Raw aggregate rows", expanded=False):
        st.dataframe(plot_df, use_container_width=True, hide_index=True)


def render_status_strip(
    events: pd.DataFrame,
    alerts: pd.DataFrame,
    aggregates: pd.DataFrame,
) -> None:
    status_label, _ = pipeline_status(events, STALE_AFTER_SECONDS)
    latest = latest_event_timestamp(events)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pipeline", status_label)
    c2.metric("Readings", len(events))
    c3.metric("Alerts", len(alerts))
    c4.metric("Updated", format_event_time(latest).replace(" UTC", "") if latest else "—")


def render_dashboard_body(
    events: pd.DataFrame,
    aggregates: pd.DataFrame,
    alerts: pd.DataFrame,
) -> None:
    """Main dashboard tabs only — must not use st.sidebar (fragment-safe)."""
    available_cities = (
        sorted(events["city"].dropna().unique().tolist()) if not events.empty else DEFAULT_CITIES
    )
    if "table_city_filter" not in st.session_state:
        st.session_state.table_city_filter = available_cities

    selected_cities = st.session_state.get("table_city_filter", available_cities)
    render_status_strip(events, alerts, aggregates)
    st.divider()

    events_filtered = filter_by_cities(events, selected_cities)
    alerts_filtered = filter_by_cities(alerts, selected_cities)
    aggregates_filtered = filter_by_cities(aggregates, selected_cities)

    snapshot = latest_reading_per_city(events_filtered)
    recent = events_filtered

    tab_dashboard, tab_alerts, tab_aggregates, tab_forecast = st.tabs(
        ["🌍 Overview", "🚨 Alerts", "📊 Aggregates", "📈 Forecast"]
    )

    with tab_dashboard:
        render_dashboard_tab(snapshot, recent, available_cities)
    with tab_alerts:
        render_alerts_tab(alerts_filtered)
    with tab_aggregates:
        render_aggregates_tab(aggregates_filtered)
    with tab_forecast:
        render_forecast_tab(events_filtered)

    st.caption(f"Refreshed {format_event_time(datetime.now(timezone.utc))}")


def main() -> None:
    _inject_styles()

    st.title(APP_NAME)
    st.caption(APP_TAGLINE)
    st.divider()

    if LIVE_MODE and not OPENWEATHER_API_KEY:
        st.error("Add `OPENWEATHER_API_KEY` to Streamlit secrets or `.env`.")

    st.sidebar.markdown("### Settings")
    refresh_seconds, auto_refresh = render_sidebar_refresh()
    st.session_state.refresh_seconds = refresh_seconds

    if "table_city_filter" not in st.session_state:
        st.session_state.table_city_filter = DEFAULT_CITIES

    run_every = timedelta(seconds=refresh_seconds) if auto_refresh else None

    @st.fragment(run_every=run_every)
    def refreshable_dashboard() -> None:
        try:
            live_events, live_aggregates, live_alerts = get_dashboard_data()
        except ValueError as exc:
            st.error(str(exc))
            live_events = st.session_state.get("event_history", pd.DataFrame())
            live_aggregates = st.session_state.get("live_aggregates", pd.DataFrame())
            live_alerts = st.session_state.get("alert_history", pd.DataFrame())
        render_dashboard_body(live_events, live_aggregates, live_alerts)

    refreshable_dashboard()


if __name__ == "__main__":
    main()
