"""Persist alerts and optionally notify Slack."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from config import ALERT_COOLDOWN_SECONDS, ALERTS_PATH, SENT_ALERTS_FILE, SLACK_WEBHOOK_URL


def _ensure_dirs() -> None:
    ALERTS_PATH.mkdir(parents=True, exist_ok=True)


def _load_sent_keys() -> dict[str, float]:
    if not SENT_ALERTS_FILE.exists():
        return {}
    try:
        return json.loads(SENT_ALERTS_FILE.read_text())
    except json.JSONDecodeError:
        return {}


def _save_sent_keys(keys: dict[str, float]) -> None:
    _ensure_dirs()
    SENT_ALERTS_FILE.write_text(json.dumps(keys, indent=2))


def _alert_key(alert: dict) -> str:
    return f"{alert['city']}:{alert['metric']}:{alert['alert_type']}"


def should_notify(alert: dict, cooldown_seconds: int = ALERT_COOLDOWN_SECONDS) -> bool:
    sent = _load_sent_keys()
    key = _alert_key(alert)
    now = datetime.now(tz=timezone.utc).timestamp()
    last_sent = sent.get(key)
    if last_sent and now - last_sent < cooldown_seconds:
        return False
    sent[key] = now
    _save_sent_keys(sent)
    return True


def persist_alerts(alerts_df: pd.DataFrame) -> Path | None:
    if alerts_df.empty:
        return None

    _ensure_dirs()
    output = alerts_df.copy()
    output["detected_at"] = datetime.now(tz=timezone.utc).isoformat()

    alerts_file = ALERTS_PATH / "alerts.parquet"
    if alerts_file.exists():
        existing = pd.read_parquet(alerts_file)
        output = pd.concat([existing, output], ignore_index=True)

    output.to_parquet(alerts_file, index=False)
    return alerts_file


def send_slack_alert(message: str, webhook_url: str | None = None) -> bool:
    webhook = webhook_url or SLACK_WEBHOOK_URL
    if not webhook:
        print("Slack webhook not configured; skipping notification.")
        return False

    response = requests.post(
        webhook,
        json={"text": message},
        timeout=10,
    )
    response.raise_for_status()
    return True


def process_alerts(alerts_df: pd.DataFrame) -> int:
    """Persist alerts and send Slack for new notifications."""
    if alerts_df.empty:
        return 0

    persist_alerts(alerts_df)
    sent_count = 0
    for alert in alerts_df.to_dict(orient="records"):
        if not should_notify(alert):
            continue
        severity = alert.get("severity", "medium").upper()
        message = f"[{severity}] {alert['message']}"
        try:
            if send_slack_alert(message):
                sent_count += 1
                print(f"Slack alert sent: {message}")
        except requests.RequestException as exc:
            print(f"Failed to send Slack alert: {exc}")
    return sent_count
