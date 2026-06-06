"""Load pipeline outputs for the dashboard and anomaly engine."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import DEMO_MODE, storage_paths


def _read_parquet_tree(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    files = sorted(path.rglob("*.parquet"))
    if not files:
        return pd.DataFrame()
    try:
        frames = [pd.read_parquet(file) for file in files]
        return pd.concat(frames, ignore_index=True)
    except (FileNotFoundError, OSError, ValueError):
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


def _shift_timestamps_to_now(df: pd.DataFrame) -> pd.DataFrame:
    """Make demo sample data appear current (max event_time ≈ now)."""
    if df.empty:
        return df
    out = with_event_time(df.copy())
    latest = out["event_time"].max()
    if pd.isna(latest):
        return out
    offset = datetime.now(timezone.utc) - latest.to_pydatetime().astimezone(timezone.utc)
    out["event_time"] = out["event_time"] + offset
    out["timestamp"] = (out["event_time"].astype("int64") // 10**9).astype(int)
    return out


def load_events(limit: int | None = None) -> pd.DataFrame:
    events_path, _, _ = storage_paths()
    events = _read_parquet_tree(events_path)
    if events.empty:
        return events

    if {"city", "timestamp"}.issubset(events.columns):
        events = events.drop_duplicates(subset=["city", "timestamp"], keep="last")

    events = with_event_time(events.sort_values("timestamp"))
    if DEMO_MODE:
        events = _shift_timestamps_to_now(events)
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
    _, aggregates_path, _ = storage_paths()
    aggregates = _read_parquet_tree(aggregates_path)
    if aggregates.empty:
        return aggregates
    if "window_start" in aggregates.columns:
        aggregates = aggregates.copy()
        aggregates["window_start"] = pd.to_datetime(aggregates["window_start"], utc=True)
        aggregates = aggregates.sort_values("window_start")
        if DEMO_MODE and not aggregates.empty:
            latest = aggregates["window_start"].max()
            offset = datetime.now(timezone.utc) - latest.to_pydatetime().astimezone(timezone.utc)
            aggregates["window_start"] = aggregates["window_start"] + offset
            if "window_end" in aggregates.columns:
                aggregates["window_end"] = pd.to_datetime(aggregates["window_end"], utc=True) + offset
    if limit:
        aggregates = aggregates.tail(limit)
    return aggregates.reset_index(drop=True)


def load_alerts(limit: int | None = 100) -> pd.DataFrame:
    _, _, alerts_path = storage_paths()
    alerts_file = alerts_path / "alerts.parquet"
    if not alerts_file.exists():
        return pd.DataFrame()
    alerts = pd.read_parquet(alerts_file)
    if "timestamp" in alerts.columns:
        alerts = alerts.sort_values("timestamp", ascending=False)
    if "detected_at" in alerts.columns:
        alerts["detected_at"] = pd.to_datetime(alerts["detected_at"], utc=True)
        if DEMO_MODE and not alerts.empty:
            alerts["detected_at"] = datetime.now(timezone.utc)
    if "timestamp" in alerts.columns and DEMO_MODE and not alerts.empty:
        events_path, _, _ = storage_paths()
        raw_events = _read_parquet_tree(events_path)
        if not raw_events.empty and "timestamp" in raw_events.columns:
            shifted = _shift_timestamps_to_now(raw_events)
            alerts["timestamp"] = int(shifted["timestamp"].max())
    if limit:
        alerts = alerts.head(limit)
    return alerts.reset_index(drop=True)
