# Real-Time Weather Intelligence Platform

A real-time weather analytics pipeline that ingests live **OpenWeatherMap** data through **Apache Kafka**, processes it with **Spark Structured Streaming** into a **Parquet data lake**, detects **anomalies** against rolling baselines, sends **Slack alerts**, and visualizes insights in a **Streamlit** dashboard.

**Repository:** [github.com/Architgupta20/Weather-Data-Dashboard](https://github.com/Architgupta20/Weather-Data-Dashboard)

---

## Architecture

```text
OpenWeatherMap API
        │
        ▼
   producer.py  ──►  Kafka (topic: weather_data)
                           │
                           ▼
              consumer_spark.py (Spark Structured Streaming)
                     │                │
                     ▼                ▼
         data/weather/events/   data/weather/aggregates/
           (Parquet, by city)     (5-min window stats)
                     │
                     ▼
           anomaly_detector + Slack alerts
                     │
                     ▼
              dashboard.py (Streamlit)
```

---

## Features

- Live weather data for 10 global cities
- Kafka producer and Spark Structured Streaming consumer
- Parquet lake storage partitioned by city and date
- 5-minute windowed aggregates (avg temp, humidity, wind)
- Rolling-baseline anomaly detection (z-score + absolute thresholds)
- Optional Slack notifications with cooldown deduplication
- Streamlit dashboard with **Dashboard**, **Alerts**, and **Aggregates** tabs

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python |
| Data source | OpenWeatherMap API |
| Messaging | Apache Kafka |
| Stream processing | Apache Spark (Structured Streaming) |
| Storage | Parquet (PyArrow) |
| Analytics | pandas, custom anomaly detection |
| Visualization | Streamlit, Plotly |
| Alerts | Slack incoming webhooks (optional) |
| Config | python-dotenv |

---

## Project Structure

```text
├── producer.py           # Publishes live weather records to Kafka
├── consumer_spark.py     # Spark streaming → Parquet + aggregates + alerts
├── dashboard.py          # Streamlit UI (events, alerts, aggregates)
├── anomaly_detector.py   # Rolling-baseline + threshold anomaly rules
├── alerts.py             # Alert persistence + Slack notifications
├── data_loader.py        # Parquet loaders for dashboard
├── config.py             # Paths and environment configuration
├── requirements.txt
├── .env.example
└── README.md
```

Runtime data is written under `data/` (gitignored).

---

## Prerequisites

- Python 3.10+
- Java 11+ (required by Spark)
- Apache Kafka on `localhost:9092`
- OpenWeatherMap API key
- Optional: Slack incoming webhook URL

### Install Kafka & Java (macOS)

```bash
brew install kafka openjdk@11
```

---

## Setup

```bash
git clone https://github.com/Architgupta20/Weather-Data-Dashboard.git
cd Weather-Data-Dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```dotenv
OPENWEATHER_API_KEY=your_key_here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ   # optional
```

---

## Kafka

```bash
zookeeper-server-start /opt/homebrew/etc/kafka/zookeeper.properties
kafka-server-start /opt/homebrew/etc/kafka/server.properties
```

Create the topic once:

```bash
kafka-topics --create \
  --topic weather_data \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

---

## Run

Use **four terminals** (venv activated in each):

| Terminal | Command |
|----------|---------|
| 1 | `python producer.py` |
| 2 | `python consumer_spark.py` |
| 3 | `streamlit run dashboard.py` |
| 4 | Kafka + Zookeeper (if not already running) |

Open the Streamlit URL (typically http://localhost:8501).

---

## Anomaly Detection

For each city and metric (`temperature`, `humidity`, `wind_speed`):

- **Z-score alerts:** compare live values to a rolling baseline (default: last 7 days, min 5 samples)
- **Absolute alerts:** heat wave (≥ 40°C), cold snap (≤ -5°C), extreme humidity (≥ 95%), high wind (≥ 15 m/s)

Alerts are stored in `data/alerts/alerts.parquet`. If `SLACK_WEBHOOK_URL` is set, new alerts are posted to Slack (1-hour cooldown per alert type by default).

Tune via `.env`: `ANOMALY_Z_THRESHOLD`, `BASELINE_DAYS`, `ALERT_COOLDOWN_SECONDS`.

---

## Author

**Archit Gupta**  
📧 [garchit1999@gmail.com](mailto:garchit1999@gmail.com)  
🔗 [LinkedIn](https://www.linkedin.com/in/archit-gupta-23ab7b1a3)
