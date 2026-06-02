"""Static coordinates for tracked cities (map visualization)."""

from __future__ import annotations

# lat, lon (WGS84) — aligned with producer.py city list
CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "Berlin": (52.52, 13.405),
    "Delhi": (28.6139, 77.209),
    "Dubai": (25.2048, 55.2708),
    "London": (51.5074, -0.1278),
    "New York": (40.7128, -74.006),
    "Paris": (48.8566, 2.3522),
    "Singapore": (1.3521, 103.8198),
    "Sydney": (-33.8688, 151.2093),
    "Tokyo": (35.6762, 139.6503),
    "Toronto": (43.6532, -79.3832),
}


def attach_coordinates(df):
    """Add lat/lon columns; unknown cities get NaN coordinates."""
    if df.empty or "city" not in df.columns:
        return df
    out = df.copy()
    out["lat"] = out["city"].map(lambda name: CITY_COORDINATES.get(name, (None, None))[0])
    out["lon"] = out["city"].map(lambda name: CITY_COORDINATES.get(name, (None, None))[1])
    return out
