import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent

# Dashboard data source (priority: LIVE_MODE > DEMO_MODE > local Parquet pipeline)
LIVE_MODE = os.getenv("LIVE_MODE", "false").lower() in ("1", "true", "yes")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes")
SAMPLE_DATA_ROOT = PROJECT_ROOT / "sample_data"
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

TRACKED_CITIES = [
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

# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "weather_data")
KAFKA_STARTING_OFFSETS = os.getenv("KAFKA_STARTING_OFFSETS", "latest")

# Storage
EVENTS_PATH = PROJECT_ROOT / "data" / "weather" / "events"
AGGREGATES_PATH = PROJECT_ROOT / "data" / "weather" / "aggregates"
ALERTS_PATH = PROJECT_ROOT / "data" / "alerts"
CHECKPOINT_EVENTS = PROJECT_ROOT / "data" / "checkpoints" / "events"
CHECKPOINT_AGGREGATES = PROJECT_ROOT / "data" / "checkpoints" / "aggregates"
SENT_ALERTS_FILE = ALERTS_PATH / ".sent_alert_keys.json"

# Alerts
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
ANOMALY_Z_THRESHOLD = float(os.getenv("ANOMALY_Z_THRESHOLD", "2.5"))
BASELINE_DAYS = int(os.getenv("BASELINE_DAYS", "7"))
MIN_BASELINE_SAMPLES = int(os.getenv("MIN_BASELINE_SAMPLES", "5"))
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "3600"))

# Spark
SPARK_APP_NAME = os.getenv("SPARK_APP_NAME", "WeatherStructuredStreaming")
WINDOW_DURATION = os.getenv("WINDOW_DURATION", "5 minutes")
WATERMARK_DELAY = os.getenv("WATERMARK_DELAY", "10 minutes")
TRIGGER_INTERVAL = os.getenv("TRIGGER_INTERVAL", "30 seconds")


def storage_paths() -> tuple[Path, Path, Path]:
    """Return (events, aggregates, alerts) paths for demo or local pipeline data."""
    if LIVE_MODE:
        return EVENTS_PATH, AGGREGATES_PATH, ALERTS_PATH
    if DEMO_MODE:
        return (
            SAMPLE_DATA_ROOT / "weather" / "events",
            SAMPLE_DATA_ROOT / "weather" / "aggregates",
            SAMPLE_DATA_ROOT / "alerts",
        )
    return EVENTS_PATH, AGGREGATES_PATH, ALERTS_PATH
