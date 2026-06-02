"""Derived weather comfort metrics for the dashboard."""

from __future__ import annotations

import math

import pandas as pd

from city_geo import attach_coordinates


def heat_index_celsius(temperature_c: float, humidity_pct: float) -> float:
    """
    NOAA Rothfusz heat index (°C).
    Below ~27°C actual temp, returns air temperature (heat index not defined).
    """
    if humidity_pct < 0 or humidity_pct > 100:
        humidity_pct = max(0.0, min(100.0, humidity_pct))

    temp_f = temperature_c * 9.0 / 5.0 + 32.0
    rh = float(humidity_pct)

    if temp_f < 80.0:
        return round(temperature_c, 1)

    hi = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * rh
        - 0.22475541 * temp_f * rh
        - 0.00683783 * temp_f * temp_f
        - 0.05481717 * rh * rh
        + 0.00122874 * temp_f * temp_f * rh
        + 0.00085282 * temp_f * rh * rh
        - 0.00000199 * temp_f * temp_f * rh * rh
    )

    if rh < 13.0 and 80.0 <= temp_f <= 112.0:
        hi -= ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(temp_f - 95.0)) / 17.0)
    if rh > 85.0 and 80.0 <= temp_f <= 87.0:
        hi += ((rh - 85.0) / 10.0) * ((87.0 - temp_f) / 5.0)

    hi_c = (hi - 32.0) * 5.0 / 9.0
    return round(max(hi_c, temperature_c), 1)


def comfort_label(heat_index_c: float) -> str:
    """Human-readable comfort band from heat index (°C)."""
    if heat_index_c < 27.0:
        return "Comfortable"
    if heat_index_c < 32.0:
        return "Warm"
    if heat_index_c < 39.0:
        return "Hot — caution"
    if heat_index_c < 46.0:
        return "Very hot — danger"
    return "Extreme heat"


def enrich_weather_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Add heat index, comfort label, and map coordinates."""
    if df.empty:
        return df

    out = attach_coordinates(df)
    if not {"temperature", "humidity"}.issubset(out.columns):
        return out

    out["heat_index"] = out.apply(
        lambda row: heat_index_celsius(float(row["temperature"]), float(row["humidity"])),
        axis=1,
    )
    out["comfort"] = out["heat_index"].map(comfort_label)
    return out
