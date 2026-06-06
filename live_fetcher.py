"""Fetch live weather directly from OpenWeatherMap (Streamlit Cloud / hosted demo)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests

from config import OPENWEATHER_API_KEY, TRACKED_CITIES

CURRENT_WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "http://api.openweathermap.org/data/2.5/forecast"

METRIC_TO_FORECAST_KEY = {
    "temperature": ("main", "temp"),
    "humidity": ("main", "humidity"),
    "wind_speed": ("wind", "speed"),
}


def _require_api_key() -> str:
    if not OPENWEATHER_API_KEY:
        raise ValueError(
            "OPENWEATHER_API_KEY is not set. Add it to .env or Streamlit Cloud secrets."
        )
    return OPENWEATHER_API_KEY


def _parse_current_record(payload: dict) -> dict:
    ts = datetime.fromtimestamp(payload["dt"], tz=timezone.utc)
    return {
        "timestamp": int(payload["dt"]),
        "city": payload["name"],
        "temperature": float(payload["main"]["temp"]),
        "humidity": float(payload["main"]["humidity"]),
        "wind_speed": float(payload["wind"]["speed"]),
        "weather_condition": payload["weather"][0]["description"],
        "event_time": ts,
    }


def fetch_city_current(city: str) -> dict | None:
    api_key = _require_api_key()
    response = requests.get(
        CURRENT_WEATHER_URL,
        params={"q": city, "appid": api_key, "units": "metric"},
        timeout=15,
    )
    if response.status_code != 200:
        return None
    return _parse_current_record(response.json())


def fetch_all_cities_current() -> pd.DataFrame:
    """Latest reading for each tracked city from OpenWeather."""
    rows: list[dict] = []
    for city in TRACKED_CITIES:
        record = fetch_city_current(city)
        if record:
            rows.append(record)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def fetch_city_forecast(city: str, metric: str, steps: int = 12) -> pd.DataFrame:
    """
    Return OpenWeather 5-day / 3-hour forecast as ds + yhat (+ simple band).
    steps caps how many future points to return.
    """
    api_key = _require_api_key()
    if metric not in METRIC_TO_FORECAST_KEY:
        raise ValueError(f"Unsupported forecast metric: {metric}")

    response = requests.get(
        FORECAST_URL,
        params={"q": city, "appid": api_key, "units": "metric"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()

    section, field = METRIC_TO_FORECAST_KEY[metric]
    rows: list[dict] = []
    for item in payload["list"][:steps]:
        value = float(item[section][field])
        rows.append(
            {
                "ds": datetime.fromtimestamp(item["dt"], tz=timezone.utc),
                "yhat": value,
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    margin = max(float(df["yhat"].std()) * 0.3, 0.5) if len(df) > 1 else 0.5
    df["yhat_lower"] = df["yhat"] - margin
    df["yhat_upper"] = df["yhat"] + margin
    return df
