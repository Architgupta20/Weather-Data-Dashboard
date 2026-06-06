"""Streamlit dashboard for weather events, aggregates, and anomaly alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import DEMO_MODE, LIVE_MODE, OPENWEATHER_API_KEY, TRACKED_CITIES
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

st.set_page_config(page_title="Weather Intelligence Dashboard", layout="wide")


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


def render_sidebar_status(events: pd.DataFrame, alerts: pd.DataFrame, aggregates: pd.DataFrame) -> None:
    st.sidebar.subheader("Pipeline status")
    status_label, status_level = pipeline_status(events, STALE_AFTER_SECONDS)
    if status_level == "success":
        st.sidebar.success(status_label)
    elif status_level == "warning":
        st.sidebar.warning(status_label)
    else:
        st.sidebar.error(status_label)

    latest = latest_event_timestamp(events)
    st.sidebar.metric("Total events", len(events))
    st.sidebar.metric("Total alerts", len(alerts))
    st.sidebar.metric("Aggregate windows", len(aggregates))
    st.sidebar.caption(f"Last update: {format_event_time(latest)}")

    if not events.empty and latest is not None:
        latest_row = enrich_weather_frame(with_event_time(events).sort_values("timestamp")).iloc[-1]
        feels = (
            f", feels {latest_row['heat_index']:.1f}°C"
            if "heat_index" in latest_row.index
            else ""
        )
        st.sidebar.caption(
            f"Latest reading: **{latest_row['city']}** — "
            f"{latest_row['temperature']:.1f}°C{feels}, {latest_row['weather_condition']}"
        )


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
        landcolor="#e8e8e8",
        showcountries=True,
        countrycolor="#bdbdbd",
        showocean=True,
        oceancolor="#d6eaf8",
    )
    fig.update_layout(
        title="Global snapshot (marker color = heat index)",
        height=440,
        margin=dict(l=0, r=0, t=48, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_dashboard_tab(snapshot: pd.DataFrame, recent: pd.DataFrame) -> None:
    if snapshot.empty:
        st.warning(
            "No event data for selected cities. Start `producer.py` and "
            "`consumer_spark.py` after Kafka is running."
        )
        return

    snapshot = enrich_weather_frame(snapshot)
    recent = enrich_weather_frame(recent)

    st.subheader("World map")
    render_world_map(snapshot)

    st.subheader("Latest reading per city")
    display_cols = [
        c
        for c in [
            "city",
            "event_time",
            "temperature",
            "heat_index",
            "comfort",
            "humidity",
            "wind_speed",
            "weather_condition",
        ]
        if c in snapshot.columns
    ]
    st.dataframe(
        snapshot[display_cols],
        use_container_width=True,
        hide_index=True,
    )

    hottest = snapshot.loc[snapshot["temperature"].idxmax()]
    most_uncomfortable = snapshot.loc[snapshot["heat_index"].idxmax()]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Avg temp (°C)", round(snapshot["temperature"].mean(), 1))
    col2.metric("Avg feels like (°C)", round(snapshot["heat_index"].mean(), 1))
    col3.metric("Avg humidity (%)", round(snapshot["humidity"].mean(), 1))
    col4.metric("Hottest", f"{hottest['city']} ({hottest['temperature']:.1f}°C)")
    col5.metric(
        "Highest heat index",
        f"{most_uncomfortable['city']} ({most_uncomfortable['heat_index']:.1f}°C)",
    )

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(
            px.bar(
                snapshot.sort_values("temperature", ascending=False),
                x="city",
                y="temperature",
                color="temperature",
                color_continuous_scale="RdYlBu_r",
                title="Current temperature by city",
            ),
            use_container_width=True,
        )
    with chart_col2:
        st.plotly_chart(
            px.scatter(
                snapshot,
                x="temperature",
                y="heat_index",
                color="city",
                size="humidity",
                hover_data=["weather_condition", "comfort"],
                title="Temperature vs heat index (feels like)",
            ),
            use_container_width=True,
        )

    with st.expander("Recent event history (last 20 records)"):
        if recent.empty:
            st.caption("No recent rows for current city filter.")
        else:
            st.dataframe(recent.tail(20), use_container_width=True, hide_index=True)


def render_alerts_tab(alerts: pd.DataFrame) -> None:
    st.subheader("Anomaly alerts")
    if alerts.empty:
        st.info(
            "No alerts yet. Alerts appear when metrics deviate from a rolling baseline "
            "or cross absolute thresholds (heat wave, cold snap, etc.)."
        )
        return

    col1, col2 = st.columns(2)
    severities = sorted(alerts["severity"].dropna().unique()) if "severity" in alerts.columns else []
    with col1:
        severity_filter = st.multiselect(
            "Severity",
            options=severities,
            default=severities,
            key="alert_severity_filter",
        )
    with col2:
        last_24h_only = st.checkbox("Last 24 hours only", value=False, key="alert_24h")

    filtered = alerts.copy()
    if severity_filter and "severity" in filtered.columns:
        filtered = filtered[filtered["severity"].isin(severity_filter)]
    if last_24h_only and "detected_at" in filtered.columns:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        filtered = filtered[filtered["detected_at"] >= cutoff]
    elif last_24h_only and "timestamp" in filtered.columns:
        cutoff_ts = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
        filtered = filtered[filtered["timestamp"] >= cutoff_ts]

    high_count = int((filtered["severity"] == "high").sum()) if "severity" in filtered.columns else 0
    m1, m2 = st.columns(2)
    m1.metric("Alerts shown", len(filtered))
    m2.metric("High severity", high_count)

    display_cols = [
        c
        for c in [
            "detected_at",
            "timestamp",
            "city",
            "metric",
            "alert_type",
            "severity",
            "value",
            "message",
        ]
        if c in filtered.columns
    ]
    st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

    if not filtered.empty and "severity" in filtered.columns:
        st.plotly_chart(
            px.histogram(
                filtered,
                x="city",
                color="severity",
                title="Alerts by city and severity",
            ),
            use_container_width=True,
        )


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


def get_dashboard_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if LIVE_MODE:
        history = st.session_state.get("event_history", pd.DataFrame())
        events, aggregates, alerts, updated_history = refresh_live_data(history)
        st.session_state.event_history = updated_history
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

    st.info("Model used: **OpenWeather 5-day forecast (live API)**")
    m1, m2 = st.columns(2)
    m1.metric(f"Next {metric} forecast", round(float(forecast.iloc[0]["yhat"]), 2))
    m2.metric("Source", "OpenWeather /forecast")

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
    st.plotly_chart(fig, use_container_width=True)


def render_forecast_tab(events: pd.DataFrame) -> None:
    st.subheader("Short-term forecast")
    st.caption(
        "Forecasts the next few intervals using historical Parquet data. "
        "Refreshes with sidebar auto-refresh."
    )

    events = enrich_weather_frame(events)
    cities = sorted(events["city"].dropna().unique().tolist()) if not events.empty else DEFAULT_CITIES
    metric_options = [m for m in FORECAST_METRICS if events.empty or m in events.columns]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        city = st.selectbox("City", options=cities, key="forecast_city")
    with col2:
        metric = st.selectbox(
            "Metric",
            options=metric_options,
            format_func=lambda m: FORECAST_METRICS[m],
            key="forecast_metric",
        )
    with col3:
        if LIVE_MODE:
            st.caption("Model")
            st.write("OpenWeather live forecast")
            method_pref = "auto"
        else:
            method_pref = st.selectbox(
                "Model",
                options=list(FORECAST_METHODS.keys()),
                format_func=lambda k: FORECAST_METHODS[k],
                key="forecast_method",
            )
    with col4:
        periods = st.slider("Forecast steps", min_value=3, max_value=12, value=6, key="forecast_periods")

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

    st.info(f"Model used: **{result.method.replace('_', ' ')}**")

    m1, m2, m3 = st.columns(3)
    if result.forecast.empty:
        st.warning("Forecast could not be generated.")
        return

    next_value = float(result.forecast.iloc[0]["yhat"])
    m1.metric(f"Next {metric} forecast", round(next_value, 2))
    m2.metric("Backtest MAE", "—" if result.mae is None else round(result.mae, 2))
    m3.metric("Backtest RMSE", "—" if result.rmse is None else round(result.rmse, 2))

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
    st.plotly_chart(fig, use_container_width=True)

    if not result.holdout_actual.empty and not result.holdout_predicted.empty:
        st.subheader("Holdout validation (recent history)")
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
            title="Forecast vs actual on held-out recent points",
            xaxis_title="Time (UTC)",
            yaxis_title=FORECAST_METRICS.get(metric, metric),
        )
        st.plotly_chart(holdout_fig, use_container_width=True)


def render_aggregates_tab(aggregates: pd.DataFrame) -> None:
    st.subheader("Spark 5-minute window aggregates")
    st.caption("Tumbling windows computed by Spark Structured Streaming.")

    if aggregates.empty:
        st.info("No aggregate data yet. Start `consumer_spark.py` to populate Parquet output.")
        return

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
    metric_col = metric[0]
    max_windows = st.slider("Windows to display", min_value=6, max_value=48, value=12, step=6)

    plot_df = aggregates.tail(max_windows).copy()
    st.dataframe(plot_df, use_container_width=True, hide_index=True)

    if {"window_start", "city", metric_col}.issubset(plot_df.columns):
        st.plotly_chart(
            px.line(
                plot_df,
                x="window_start",
                y=metric_col,
                color="city",
                markers=True,
                title=f"{metric[1]} by 5-minute window",
            ),
            use_container_width=True,
        )


def render_dashboard_body(
    selected_cities: list[str],
    events: pd.DataFrame,
    aggregates: pd.DataFrame,
    alerts: pd.DataFrame,
) -> None:
    """Main dashboard tabs only — must not use st.sidebar (fragment-safe)."""

    events_filtered = filter_by_cities(events, selected_cities)
    alerts_filtered = filter_by_cities(alerts, selected_cities)
    aggregates_filtered = filter_by_cities(aggregates, selected_cities)

    snapshot = latest_reading_per_city(events_filtered)
    recent = events_filtered

    tab_dashboard, tab_alerts, tab_aggregates, tab_forecast = st.tabs(
        ["Dashboard", "Alerts", "5-min Aggregates", "Forecast"]
    )

    with tab_dashboard:
        render_dashboard_tab(snapshot, recent)
    with tab_alerts:
        render_alerts_tab(alerts_filtered)
    with tab_aggregates:
        render_aggregates_tab(aggregates_filtered)
    with tab_forecast:
        render_forecast_tab(events_filtered)

    st.caption(f"Data refreshed at {format_event_time(datetime.now(timezone.utc))}")


def main() -> None:
    st.title("Weather Intelligence Dashboard")
    if LIVE_MODE:
        st.success(
            "**Live mode** — fetching real-time weather from OpenWeather on each refresh. "
            "No Kafka or Spark required for this hosted view."
        )
        if not OPENWEATHER_API_KEY:
            st.error("Set `OPENWEATHER_API_KEY` in `.env` or Streamlit Cloud secrets.")
    elif DEMO_MODE:
        st.info(
            "**Demo mode** — bundled sample data only (static values). "
            "Use `LIVE_MODE=true` for recruiter-facing live data."
        )
    st.caption(
        "Live OpenWeather API → dashboard refresh."
        if LIVE_MODE
        else "Live data from Kafka → Spark → Parquet, with rolling-baseline anomaly detection."
        if not DEMO_MODE
        else "Sample weather intelligence dashboard for portfolio review."
    )

    st.sidebar.header("Controls")
    refresh_seconds = st.sidebar.slider("Auto-refresh (seconds)", 15, 120, 30)
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
    if st.sidebar.button("Refresh now", use_container_width=True):
        st.rerun()

    try:
        events, aggregates, alerts = get_dashboard_data()
    except ValueError as exc:
        st.error(str(exc))
        events, aggregates, alerts = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    all_cities = sorted(events["city"].dropna().unique().tolist()) if not events.empty else DEFAULT_CITIES
    selected_cities = st.sidebar.multiselect(
        "Cities",
        options=all_cities,
        default=all_cities,
        key="city_filter",
    )
    render_sidebar_status(events, alerts, aggregates)

    run_every = timedelta(seconds=refresh_seconds) if auto_refresh else None

    @st.fragment(run_every=run_every)
    def refreshable_dashboard() -> None:
        try:
            live_events, live_aggregates, live_alerts = get_dashboard_data()
        except ValueError as exc:
            st.error(str(exc))
            live_events, live_aggregates, live_alerts = events, aggregates, alerts
        render_dashboard_body(selected_cities, live_events, live_aggregates, live_alerts)

    refreshable_dashboard()


if __name__ == "__main__":
    main()
