"""Generate bundled Parquet sample data for demo / Streamlit Cloud deployment."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from anomaly_detector import detect_anomalies  # noqa: E402

CITIES = [
    "New York",
    "London",
    "Tokyo",
    "Delhi",
    "Paris",
    "Berlin",
    "Sydney",
    "Toronto",
    "Dubai",
    "Singapore",
]

# Base climate-ish profiles for plausible demo values
CITY_PROFILES = {
    "New York": (18.0, 62.0, 4.5, "partly cloudy"),
    "London": (14.0, 78.0, 5.2, "light rain"),
    "Tokyo": (22.0, 70.0, 3.1, "clear sky"),
    "Delhi": (36.0, 45.0, 2.8, "haze"),
    "Paris": (17.0, 72.0, 4.0, "overcast clouds"),
    "Berlin": (16.0, 68.0, 3.8, "scattered clouds"),
    "Sydney": (21.0, 58.0, 6.5, "clear sky"),
    "Toronto": (12.0, 55.0, 4.2, "few clouds"),
    "Dubai": (38.0, 40.0, 3.5, "clear sky"),
    "Singapore": (30.0, 82.0, 2.5, "thunderstorm"),
}

CONDITIONS = [
    "clear sky",
    "few clouds",
    "scattered clouds",
    "broken clouds",
    "overcast clouds",
    "light rain",
    "haze",
]

INTERVAL_MINUTES = 30
POINTS_PER_CITY = 48  # ~24 hours


def _generate_events() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    base_time = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    rows: list[dict] = []

    for city in CITIES:
        temp_base, hum_base, wind_base, default_cond = CITY_PROFILES[city]
        for i in range(POINTS_PER_CITY):
            ts = base_time + timedelta(minutes=INTERVAL_MINUTES * i)
            hour = ts.hour
            temp = temp_base + 4 * np.sin(2 * np.pi * hour / 24) + rng.normal(0, 0.8)
            humidity = np.clip(hum_base + rng.normal(0, 4), 20, 98)
            wind = max(0.5, wind_base + rng.normal(0, 0.6))

            # Inject a Delhi heat spike for demo alerts
            if city == "Delhi" and i >= POINTS_PER_CITY - 4:
                temp = 41.0 + rng.normal(0, 0.3)

            rows.append(
                {
                    "timestamp": int(ts.timestamp()),
                    "city": city,
                    "temperature": round(float(temp), 1),
                    "humidity": round(float(humidity), 1),
                    "wind_speed": round(float(wind), 1),
                    "weather_condition": default_cond if i % 6 else rng.choice(CONDITIONS),
                    "event_time": ts,
                    "event_date": ts.date(),
                }
            )

    return pd.DataFrame(rows)


def _write_events(events: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for (city, event_date), group in events.groupby(["city", "event_date"]):
        part_dir = out_dir / f"city={city}" / f"event_date={event_date}"
        part_dir.mkdir(parents=True, exist_ok=True)
        group.drop(columns=["event_date"]).to_parquet(part_dir / "part-0.parquet", index=False)


def _generate_aggregates(events: pd.DataFrame) -> pd.DataFrame:
    df = events.copy()
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
    return agg


def _write_aggregates(aggregates: pd.DataFrame, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for city, group in aggregates.groupby("city"):
        part_dir = out_dir / f"city={city}"
        part_dir.mkdir(parents=True, exist_ok=True)
        group.to_parquet(part_dir / "part-0.parquet", index=False)


def _generate_alerts(events: pd.DataFrame) -> pd.DataFrame:
    historical = events.sort_values("timestamp").iloc[:-10].copy()
    latest_batch = events.sort_values("timestamp").groupby("city", as_index=False).tail(1)
    alerts = detect_anomalies(latest_batch, historical)
    if alerts.empty:
        # Fallback demo alerts if thresholds did not fire
        alerts = pd.DataFrame(
            [
                {
                    "timestamp": int(events["timestamp"].max()),
                    "city": "Delhi",
                    "metric": "temperature",
                    "alert_type": "heat_wave",
                    "severity": "high",
                    "value": 41.2,
                    "baseline_mean": None,
                    "baseline_std": None,
                    "z_score": None,
                    "message": "Delhi: heat wave (temperature=41.2)",
                },
                {
                    "timestamp": int(events["timestamp"].max()),
                    "city": "Singapore",
                    "metric": "humidity",
                    "alert_type": "humidity_spike",
                    "severity": "medium",
                    "value": 88.0,
                    "baseline_mean": 82.0,
                    "baseline_std": 3.5,
                    "z_score": 2.8,
                    "message": "Singapore: humidity spike detected (88.0 vs baseline 82.0 ± 3.5, z=2.80)",
                },
            ]
        )
    alerts["detected_at"] = datetime.now(tz=timezone.utc).isoformat()
    return alerts


def main() -> None:
    sample_root = ROOT / "sample_data"
    events_dir = sample_root / "weather" / "events"
    aggregates_dir = sample_root / "weather" / "aggregates"
    alerts_dir = sample_root / "alerts"

    for path in (events_dir, aggregates_dir, alerts_dir):
        if path.exists():
            import shutil

            shutil.rmtree(path)

    events = _generate_events()
    aggregates = _generate_aggregates(events)
    alerts = _generate_alerts(events)

    _write_events(events, events_dir)
    _write_aggregates(aggregates, aggregates_dir)
    alerts_dir.mkdir(parents=True, exist_ok=True)
    alerts.to_parquet(alerts_dir / "alerts.parquet", index=False)

    print(f"Wrote {len(events)} events for {events['city'].nunique()} cities")
    print(f"Wrote {len(aggregates)} aggregate windows")
    print(f"Wrote {len(alerts)} alerts")
    print(f"Sample data root: {sample_root}")


if __name__ == "__main__":
    main()
