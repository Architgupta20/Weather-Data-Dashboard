"""Build live dashboard datasets from OpenWeather + in-session history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from anomaly_detector import detect_anomalies
from data_loader import with_event_time
from live_fetcher import fetch_all_cities_current

MAX_HISTORY_ROWS = 2000


def _compute_aggregates(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()

    df = with_event_time(history.copy())
    df["window_start"] = df["event_time"].dt.floor("5min")
    agg = (
        df.groupby(["city", "window_start"], as_index=False)
        .agg(
            avg_temperature=("temperature", "mean"),
            avg_humidity=("humidity", "mean"),
            avg_wind_speed=("wind_speed", "mean"),
            record_count=("temperature", "count"),
        )
        .sort_values(["city", "window_start"])
    )
    agg["window_end"] = agg["window_start"] + timedelta(minutes=5)
    for col in ("avg_temperature", "avg_humidity", "avg_wind_speed"):
        agg[col] = agg[col].round(2)
    return agg.tail(200).reset_index(drop=True)


def refresh_live_data(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Fetch live readings, merge session history, compute aggregates and alerts.
    Returns (all_events_history, aggregates, alerts, updated_history).
    """
    current = fetch_all_cities_current()
    if current.empty:
        return history, pd.DataFrame(), pd.DataFrame(), history

    now = datetime.now(timezone.utc)
    current = current.copy()
    current["event_time"] = now
    current["timestamp"] = int(now.timestamp())
    current = with_event_time(current)
    if history.empty:
        updated = current.copy()
    else:
        updated = pd.concat([history, current], ignore_index=True)
        updated = updated.drop_duplicates(subset=["city", "timestamp"], keep="last")
        updated = with_event_time(updated.sort_values("timestamp")).tail(MAX_HISTORY_ROWS)

    aggregates = _compute_aggregates(updated)
    alerts = detect_anomalies(current, updated.iloc[:-len(current)] if len(updated) > len(current) else pd.DataFrame())
    if not alerts.empty:
        alerts = alerts.copy()
        alerts["detected_at"] = pd.Timestamp.now(tz="UTC")

    return updated.reset_index(drop=True), aggregates, alerts.reset_index(drop=True), updated
