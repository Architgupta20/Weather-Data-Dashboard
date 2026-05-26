"""Streamlit dashboard for weather events, aggregates, and anomaly alerts."""

import time

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import load_aggregates, load_alerts, load_events

st.set_page_config(page_title="Weather Intelligence Dashboard", layout="wide")
st.title("Weather Intelligence Dashboard")
st.caption("Live data from Kafka → Spark → Parquet, with rolling-baseline anomaly detection.")

if "start_index" not in st.session_state:
    st.session_state.start_index = 0
if "refresh_count" not in st.session_state:
    st.session_state.refresh_count = 0

refresh_seconds = st.sidebar.slider("Auto-refresh (seconds)", 15, 120, 30)
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)

events = load_events()
aggregates = load_aggregates()
alerts = load_alerts()

tab_dashboard, tab_alerts, tab_aggregates = st.tabs(
    ["Dashboard", "Alerts", "5-min Aggregates"]
)

with tab_dashboard:
    if events.empty:
        st.warning(
            "No event data yet. Start `producer.py` and `consumer_spark.py` "
            "after Kafka is running."
        )
    else:
        total_rows = len(events)
        if st.session_state.start_index + 10 <= total_rows:
            batch = events.iloc[
                st.session_state.start_index : st.session_state.start_index + 10
            ]
            st.session_state.start_index += 10
            st.session_state.refresh_count += 1
        else:
            batch = events.tail(10)

        st.success(f"Dashboard refresh count: {st.session_state.refresh_count}")
        st.subheader("Latest weather batch")
        st.dataframe(batch, use_container_width=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Avg temp (°C)", round(batch["temperature"].mean(), 2))
        col2.metric("Avg humidity (%)", round(batch["humidity"].mean(), 2))
        col3.metric("Avg wind (m/s)", round(batch["wind_speed"].mean(), 2))

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.plotly_chart(
                px.line(
                    batch,
                    x="timestamp",
                    y="temperature",
                    color="city",
                    markers=True,
                    title="Temperature trends",
                ),
                use_container_width=True,
            )
        with chart_col2:
            st.plotly_chart(
                px.scatter(
                    batch,
                    x="wind_speed",
                    y="temperature",
                    color="city",
                    size="humidity",
                    hover_data=["weather_condition"],
                    title="Wind vs temperature",
                ),
                use_container_width=True,
            )

with tab_alerts:
    st.subheader("Active anomaly alerts")
    if alerts.empty:
        st.info(
            "No alerts yet. Alerts appear when metrics deviate from a rolling baseline "
            "or cross absolute thresholds (heat wave, cold snap, etc.)."
        )
    else:
        active = alerts.copy()
        if "severity" in active.columns:
            severity_filter = st.multiselect(
                "Severity",
                options=sorted(active["severity"].dropna().unique()),
                default=list(active["severity"].dropna().unique()),
            )
            active = active[active["severity"].isin(severity_filter)]

        st.metric("Total alerts stored", len(alerts))
        st.dataframe(active, use_container_width=True)

        if "severity" in active.columns and not active.empty:
            st.plotly_chart(
                px.histogram(
                    active,
                    x="city",
                    color="severity",
                    title="Alerts by city and severity",
                ),
                use_container_width=True,
            )

with tab_aggregates:
    st.subheader("Spark windowed aggregates (5-minute windows)")
    if aggregates.empty:
        st.info("No aggregate data yet. Start `consumer_spark.py` to populate Parquet output.")
    else:
        st.dataframe(aggregates.tail(50), use_container_width=True)
        if {"window_start", "avg_temperature", "city"}.issubset(aggregates.columns):
            plot_df = aggregates.copy()
            plot_df["window_start"] = pd.to_datetime(plot_df["window_start"])
            st.plotly_chart(
                px.line(
                    plot_df,
                    x="window_start",
                    y="avg_temperature",
                    color="city",
                    title="Average temperature by 5-minute window",
                ),
                use_container_width=True,
            )

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
