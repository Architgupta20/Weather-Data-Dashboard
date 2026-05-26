"""Rolling-baseline anomaly detection for streaming weather metrics."""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable

import pandas as pd

from config import ANOMALY_Z_THRESHOLD, BASELINE_DAYS, MIN_BASELINE_SAMPLES

METRICS = ("temperature", "humidity", "wind_speed")

ABSOLUTE_RULES: list[tuple[str, str, callable, str]] = [
    ("temperature", "heat_wave", lambda value: value >= 40, "high"),
    ("temperature", "cold_snap", lambda value: value <= -5, "high"),
    ("humidity", "extreme_humidity", lambda value: value >= 95, "medium"),
    ("wind_speed", "high_wind", lambda value: value >= 15, "medium"),
]

def _prepare_events(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    prepared = df.copy()
    prepared["event_time"] = pd.to_datetime(prepared["timestamp"], unit="s", utc=True)
    for column in METRICS:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")
    return prepared.dropna(subset=["city", *METRICS])


def _baseline_stats(historical: pd.DataFrame) -> pd.DataFrame:
    if historical.empty:
        return pd.DataFrame(columns=["city", "metric", "mean", "std", "sample_count"])

    cutoff = historical["event_time"].max() - timedelta(days=BASELINE_DAYS)
    window = historical[historical["event_time"] >= cutoff]

    rows: list[dict] = []
    for city, city_df in window.groupby("city"):
        for metric in METRICS:
            series = city_df[metric].dropna()
            if len(series) < MIN_BASELINE_SAMPLES:
                continue
            rows.append(
                {
                    "city": city,
                    "metric": metric,
                    "mean": float(series.mean()),
                    "std": float(series.std(ddof=0)),
                    "sample_count": int(len(series)),
                }
            )
    return pd.DataFrame(rows)


def _z_score_alerts(row: pd.Series, baselines: pd.DataFrame) -> list[dict]:
    alerts: list[dict] = []
    city_baselines = baselines[baselines["city"] == row["city"]]
    if city_baselines.empty:
        return alerts

    for metric in METRICS:
        metric_row = city_baselines[city_baselines["metric"] == metric]
        if metric_row.empty:
            continue

        mean = float(metric_row.iloc[0]["mean"])
        std = float(metric_row.iloc[0]["std"])
        value = float(row[metric])
        if std <= 0:
            continue

        z_score = (value - mean) / std
        if abs(z_score) < ANOMALY_Z_THRESHOLD:
            continue

        direction = "spike" if z_score > 0 else "drop"
        severity = "high" if abs(z_score) >= 3 else "medium"
        alerts.append(
            {
                "timestamp": int(row["timestamp"]),
                "city": row["city"],
                "metric": metric,
                "alert_type": f"{metric}_{direction}",
                "severity": severity,
                "value": value,
                "baseline_mean": mean,
                "baseline_std": std,
                "z_score": round(z_score, 2),
                "message": (
                    f"{row['city']}: {metric} {direction} detected "
                    f"({value:.1f} vs baseline {mean:.1f} ± {std:.1f}, z={z_score:.2f})"
                ),
            }
        )
    return alerts


def _absolute_alerts(row: pd.Series) -> list[dict]:
    alerts: list[dict] = []
    for metric, alert_type, rule, severity in ABSOLUTE_RULES:
        value = float(row[metric])
        if not rule(value):
            continue
        alerts.append(
            {
                "timestamp": int(row["timestamp"]),
                "city": row["city"],
                "metric": metric,
                "alert_type": alert_type,
                "severity": severity,
                "value": value,
                "baseline_mean": None,
                "baseline_std": None,
                "z_score": None,
                "message": f"{row['city']}: {alert_type.replace('_', ' ')} "
                f"({metric}={value:.1f})",
            }
        )
    return alerts


def detect_anomalies(
    new_records: pd.DataFrame,
    historical_records: pd.DataFrame,
) -> pd.DataFrame:
    """Return alert rows for records that deviate from rolling baselines."""
    new_prepared = _prepare_events(new_records)
    if new_prepared.empty:
        return pd.DataFrame()

    history = _prepare_events(historical_records)
    baselines = _baseline_stats(history)

    alert_rows: list[dict] = []
    seen_keys: set[tuple] = set()

    for _, row in new_prepared.iterrows():
        candidates: Iterable[dict] = []
        candidates = list(_absolute_alerts(row))
        if not baselines.empty:
            candidates.extend(_z_score_alerts(row, baselines))

        for alert in candidates:
            dedupe_key = (alert["city"], alert["metric"], alert["alert_type"])
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            alert_rows.append(alert)

    if not alert_rows:
        return pd.DataFrame()

    return pd.DataFrame(alert_rows)
