"""Load pipeline outputs for the dashboard and anomaly engine."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import AGGREGATES_PATH, ALERTS_PATH, EVENTS_PATH


def _read_parquet_tree(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except (FileNotFoundError, OSError):
        return pd.DataFrame()


def with_event_time(events: pd.DataFrame) -> pd.DataFrame:
    """Ensure a timezone-aware event_time column exists."""
    if events.empty:
        return events
    df = events.copy()
    if "event_time" in df.columns:
        df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
    else:
        df["event_time"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    return df


def load_events(limit: int | None = None) -> pd.DataFrame:
    events = _read_parquet_tree(EVENTS_PATH)
    if events.empty:
        return events

    if {"city", "timestamp"}.issubset(events.columns):
        events = events.drop_duplicates(subset=["city", "timestamp"], keep="last")

    events = with_event_time(events.sort_values("timestamp"))
    if limit:
        events = events.tail(limit)
    return events.reset_index(drop=True)


def latest_reading_per_city(events: pd.DataFrame) -> pd.DataFrame:
    """Most recent record for each city."""
    events = with_event_time(events)
    if events.empty or "city" not in events.columns:
        return events
    return (
        events.sort_values("timestamp")
        .groupby("city", as_index=False)
        .tail(1)
        .sort_values("city")
        .reset_index(drop=True)
    )


def latest_event_timestamp(events: pd.DataFrame) -> datetime | None:
    events = with_event_time(events)
    if events.empty:
        return None
    ts = events["event_time"].max()
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def load_aggregates(limit: int | None = 200) -> pd.DataFrame:
    aggregates = _read_parquet_tree(AGGREGATES_PATH)
    if aggregates.empty:
        return aggregates
    if "window_start" in aggregates.columns:
        aggregates = aggregates.copy()
        aggregates["window_start"] = pd.to_datetime(aggregates["window_start"], utc=True)
        aggregates = aggregates.sort_values("window_start")
    if limit:
        aggregates = aggregates.tail(limit)
    return aggregates.reset_index(drop=True)


def load_alerts(limit: int | None = 100) -> pd.DataFrame:
    alerts_file = ALERTS_PATH / "alerts.parquet"
    if not alerts_file.exists():
        return pd.DataFrame()
    alerts = pd.read_parquet(alerts_file)
    if "timestamp" in alerts.columns:
        alerts = alerts.sort_values("timestamp", ascending=False)
    if "detected_at" in alerts.columns:
        alerts["detected_at"] = pd.to_datetime(alerts["detected_at"], utc=True)
    if limit:
        alerts = alerts.head(limit)
    return alerts.reset_index(drop=True)
