# Real-Time Weather Intelligence Platform

**Real-Time Weather Intelligence Platform** — a live weather analytics system that ingests **OpenWeatherMap** data through **Apache Kafka**, processes it with **Spark Structured Streaming** into a **Parquet data lake**, detects **anomalies** against rolling baselines, sends **Slack alerts**, and visualizes insights in a **Streamlit** UI.

**Repository:** [github.com/Architgupta20/Weather-Data-Dashboard](https://github.com/Architgupta20/Weather-Data-Dashboard)

---

## Live demo (recruiters — no install)

> **After Streamlit Cloud deploy:** replace the link below with your app URL.

**[Open Real-Time Weather Intelligence Platform →](https://YOUR-APP-NAME.streamlit.app)** *(coming soon)*

- **Live weather** from OpenWeather API — values update on each auto-refresh
- No Kafka, Spark, or Java required for the hosted link
- Set locally: `LIVE_MODE=true streamlit run dashboard.py` (needs `OPENWEATHER_API_KEY`)

**Full pipeline** (Kafka + Spark + Parquet lake): [Docker Compose](#quick-start-with-docker-compose) or [local run](#how-to-run-step-by-step).

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

**Data flow:** The producer fetches **one reading per city** (~10 cities), publishes to Kafka, Spark consumes and writes Parquet, and the dashboard reads Parquet. Producer and consumer must run **at the same time**.

---

## Features

- Live weather data for 10 global cities
- Kafka producer and Spark Structured Streaming consumer
- Parquet lake storage partitioned by city and date
- 5-minute windowed aggregates (avg temp, humidity, wind)
- Rolling-baseline anomaly detection (z-score + absolute thresholds)
- Optional Slack notifications with cooldown deduplication
- Streamlit UI with **Overview**, **Alerts**, **Aggregates**, and **Forecast** tabs
- Short-horizon forecasting (Prophet when installed, else Holt–Winters ETS or linear trend) with holdout MAE/RMSE
- **World map** with heat-index coloring and NOAA-style **feels-like** (heat index) in the dashboard table

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python |
| Data source | OpenWeatherMap API |
| Messaging | Apache Kafka |
| Stream processing | Apache Spark (Structured Streaming) |
| Storage | Parquet (PyArrow) |
| Analytics | pandas, statsmodels, optional Prophet, anomaly detection |
| Visualization | Streamlit, Plotly |
| Alerts | Slack incoming webhooks (optional) |
| Config | python-dotenv |

---

## Project Structure

```text
├── producer.py           # Publishes live weather records to Kafka
├── consumer_spark.py     # Spark streaming → Parquet + aggregates + alerts
├── dashboard.py          # Real-Time Weather Intelligence Platform UI
├── anomaly_detector.py   # Rolling-baseline + threshold anomaly rules
├── alerts.py             # Alert persistence + Slack notifications
├── data_loader.py        # Parquet loaders for dashboard
├── forecasting.py        # Short-horizon forecasts (Prophet / ETS / linear)
├── weather_metrics.py    # Heat index and comfort labels
├── city_geo.py           # City coordinates for map view
├── config.py             # Paths and environment configuration
├── sample_data/          # Bundled Parquet for demo / Streamlit Cloud
├── scripts/
│   └── generate_sample_data.py
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── requirements.txt
├── .env.example
└── README.md
```

Runtime data is written under `data/` (gitignored).

---

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **Python 3.10+** | Project tested with 3.13 |
| **Java 11+** | Required for Spark (`java -version`) |
| **Apache Kafka** | Homebrew Kafka 3.x / 4.x on macOS |
| **OpenWeatherMap API key** | [Get one free](https://home.openweathermap.org/api_keys) |
| **Slack webhook** | Optional, for alert notifications |

### Install on macOS (Homebrew)

```bash
brew install kafka openjdk@11
```

> **Apple Silicon:** Kafka config is usually under `/opt/homebrew/etc/kafka/`  
> **Intel Mac:** often `/usr/local/etc/kafka/`

---

## One-Time Setup

### 1. Clone and install Python dependencies

```bash
git clone https://github.com/Architgupta20/Weather-Data-Dashboard.git
cd Weather-Data-Dashboard
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
OPENWEATHER_API_KEY=your_openweather_api_key_here
SLACK_WEBHOOK_URL=                                    # optional
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=weather_data
KAFKA_STARTING_OFFSETS=latest
TRIGGER_INTERVAL=30 seconds
```

### 3. Format Kafka storage (first time only)

Homebrew Kafka 4.x uses **KRaft** (no Zookeeper). Run once:

```bash
# Stop broken background services if they were started before
brew services stop kafka 2>/dev/null
brew services stop zookeeper 2>/dev/null

export KAFKA_CLUSTER_ID=$(kafka-storage random-uuid)
kafka-storage format -t "$KAFKA_CLUSTER_ID" \
  -c /opt/homebrew/etc/kafka/kraft/server.properties
```

> If you see "already formatted", skip this step.

---

## Deploy live dashboard to Streamlit Cloud

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → select this repo.
3. **App name:** `Real-Time Weather Intelligence Platform` (or a short URL slug).
4. Main file path: `dashboard.py`
5. **Secrets** (required for live data):

```toml
LIVE_MODE = "true"
OPENWEATHER_API_KEY = "your_openweather_api_key_here"
```

6. Deploy. First load may take ~1–2 minutes while dependencies install.
7. Open the app — weather refreshes every 15–120 seconds (sidebar slider).
8. Copy the public URL into the **Live demo** section above and your resume.

> `DEMO_MODE=true` is only for offline/static fallback (no API key). Do **not** use it for recruiter links.

---

## Quick Start with Docker Compose

Run the full stack with one command (Kafka + producer + Spark consumer + dashboard):

```bash
docker compose up --build
```

Open **http://localhost:8501**.

Useful commands:

```bash
# Stop everything
docker compose down

# Stop and remove Kafka volume too (fresh Kafka state)
docker compose down -v
```

Notes:

- The dashboard reads and writes data via `./data` (bind-mounted from host).
- First consumer startup may take longer while Spark resolves Kafka connector JARs.
- If you switch between Docker and local runs, use the [clean restart](#clean-restart) section to reset stale checkpoints.

---

## How to Run (step by step)

You need **4 terminals**. Activate the venv in each:

```bash
cd Weather-Data-Dashboard   # or your clone path
source .venv/bin/activate
```

### Terminal 1 — Start Kafka (leave running)

```bash
kafka-server-start /opt/homebrew/etc/kafka/kraft/server.properties
```

Wait until you see:

- `Awaiting socket connections on 0.0.0.0:9092`
- `Kafka Server started`

> Do **not** use `zookeeper-server-start` on modern Homebrew Kafka — that command does not exist. KRaft replaces Zookeeper.

**Verify** (optional, new terminal):

```bash
kafka-topics --list --bootstrap-server localhost:9092
```

### Terminal 2 — Create Kafka topic (first time only)

```bash
kafka-topics --create \
  --topic weather_data \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

If the topic already exists, you can skip this.

### Terminal 3 — Producer (leave running)

```bash
source .venv/bin/activate
python producer.py
```

**Expected output:** lines like `Sent: {'city': 'New York', 'temperature': ...}` every few seconds, then `Waiting 30 seconds before the next round...`

- Fetches **one** weather reading per city per round (10 cities).
- Publishes to Kafka topic `weather_data`.

### Terminal 4 — Spark consumer (leave running; start right after producer)

```bash
source .venv/bin/activate
export JAVA_HOME=$(/usr/libexec/java_home)
python consumer_spark.py
```

**Important:**

- Run this **while the producer is running** — they work together.
- **First run** may take 1–2 minutes while Spark downloads Kafka connector JARs. Do not stop it.
- **Expected output:** `Batch 0: stored X events, generated Y alerts, sent Z Slack notifications.`

Writes data to:

- `data/weather/events/` — raw events (Parquet)
- `data/weather/aggregates/` — 5-minute window stats
- `data/alerts/` — anomaly alerts

### Terminal 5 — Dashboard (leave running)

```bash
source .venv/bin/activate
streamlit run dashboard.py
```

Open the URL printed in the terminal (usually **http://localhost:8501**).

- Keep this terminal open — closing it stops the website (`ERR_CONNECTION_REFUSED`).
- Refresh the browser after ~30–60 seconds once the consumer has processed a batch.

| Tab | Content |
|-----|---------|
| **Overview** | Live city table, map, and temperature charts |
| **Alerts** | Detected anomalies |
| **5-min Aggregates** | Spark windowed averages |
| **Forecast** | Next-interval forecast + confidence band and backtest metrics |

---

## Forecasting

The **Forecast** tab uses historical event Parquet data for the selected city and metric (`temperature`, `humidity`, `wind_speed`).

1. **Minimum data:** at least **12** resampled time points for that city (keep producer + consumer running for a while).
2. **Model order:** tries **Prophet** if installed; otherwise **statsmodels** exponential smoothing; otherwise a **linear trend** fallback.
3. **Validation:** holdout MAE/RMSE on the most recent segment of history.

Optional Prophet (may not install on Python 3.13+):

```bash
pip install prophet
```

`statsmodels` is included in `requirements.txt`.

---

## Run order summary

```text
1. Kafka          (Terminal 1)
2. Create topic   (once)
3. producer.py    (Terminal 3)  ──┐
4. consumer_spark (Terminal 4)  ──┴── run TOGETHER
5. streamlit      (Terminal 5)
```

| Component | Must run simultaneously with |
|-----------|-------------------------------|
| `producer.py` | `consumer_spark.py` |
| `consumer_spark.py` | `producer.py` |
| `dashboard.py` | Kafka + producer + consumer (for live data) |

---

## Slack alerts (optional)

1. Create a Slack workspace and channel (e.g. `#weather-alerts`).
2. [Create an Incoming Webhook](https://api.slack.com/messaging/webhooks) and copy the URL.
3. Add to `.env`: `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...`
4. Restart `consumer_spark.py`.

Alerts also appear in the dashboard **Alerts** tab.

---

## Anomaly detection

For each city and metric (`temperature`, `humidity`, `wind_speed`):

- **Z-score:** compares to a rolling baseline (default: last 7 days, min 5 samples)
- **Absolute rules:** heat wave (≥ 40°C), cold snap (≤ -5°C), extreme humidity (≥ 95%), high wind (≥ 15 m/s)

Tune in `.env`: `ANOMALY_Z_THRESHOLD`, `BASELINE_DAYS`, `ALERT_COOLDOWN_SECONDS`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `zookeeper-server-start: command not found` | Use KRaft: `kafka-server-start .../kraft/server.properties` (see above) |
| `Connection refused` on port 9092 | Start Kafka (Terminal 1) and wait for `Kafka Server started` |
| `Failed to find data source: kafka` | Use latest `consumer_spark.py` (includes Kafka Maven packages). Re-run consumer. |
| `No module named 'distutils'` | Use latest `consumer_spark.py` + `pip install setuptools` |
| Dashboard: `localhost refused to connect` | Run `streamlit run dashboard.py` and keep terminal open |
| Dashboard: "No event data yet" | Start **both** `producer.py` and `consumer_spark.py` |
| Same city appears many times | Duplicates from restarts. Refresh after code update, or [reset data](#clean-restart) |
| `OPENWEATHER_API_KEY` error | Copy `.env.example` → `.env` and set your API key |
| Spark / Java errors | `export JAVA_HOME=$(/usr/libexec/java_home)` before consumer |

### Clean restart

If you restarted the consumer several times and see duplicate rows, stop all processes and reset local data:

```bash
rm -rf data/checkpoints data/weather data/alerts
```

Then start again from **Terminal 1** (Kafka) through **Terminal 5** (dashboard).

---

## Stop the pipeline

Press `Ctrl+C` in each terminal, in order:

1. Streamlit (dashboard)  
2. Spark consumer  
3. Producer  
4. Kafka  

---

## Cities tracked

New York, London, Tokyo, Delhi, Paris, Berlin, Sydney, Toronto, Dubai, Singapore

Edit the `CITIES` list in `producer.py` to customize.

---

## Author

**Archit Gupta**  
📧 [garchit1999@gmail.com](mailto:garchit1999@gmail.com)  
🔗 [LinkedIn](https://www.linkedin.com/in/archit-gupta-23ab7b1a3)
