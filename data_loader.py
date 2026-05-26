"""Load pipeline outputs for the dashboard and anomaly engine."""

from __future__ import annotations

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


def load_events(limit: int | None = None) -> pd.DataFrame:
    events = _read_parquet_tree(EVENTS_PATH)
    if events.empty:
        return events

    # Drop duplicate Kafka/Spark writes (same city + timestamp)
    if {"city", "timestamp"}.issubset(events.columns):
        events = events.drop_duplicates(subset=["city", "timestamp"], keep="last")

    events = events.sort_values("timestamp")
    if limit:
        events = events.tail(limit)
    return events.reset_index(drop=True)


def load_aggregates(limit: int | None = 200) -> pd.DataFrame:
    aggregates = _read_parquet_tree(AGGREGATES_PATH)
    if aggregates.empty:
        return aggregates
    if "window_start" in aggregates.columns:
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
    if limit:
        alerts = alerts.head(limit)
    return alerts.reset_index(drop=True)
