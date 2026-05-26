# Real-Time Weather Data Analytics Dashboard

A real-time weather analytics pipeline that fetches live data from the **OpenWeatherMap API**, streams it through **Apache Kafka**, batches and stores it with **pandas**, and visualizes insights in a **Streamlit** dashboard with **Plotly** charts.

**Repository:** [github.com/Architgupta20/Weather-Data-Dashboard](https://github.com/Architgupta20/Weather-Data-Dashboard)

---

## Architecture

```text
OpenWeatherMap API
        │
        ▼
  producer.ipynb  ──►  Kafka (topic: weather_data)
                              │
                              ▼
                      consumer.ipynb  ──►  weather_data.csv
                                              │
                                              ▼
                                    dashboard.py (Streamlit)
```

---

## Features

- Live weather data for 10 global cities
- Kafka producer/consumer streaming pipeline
- Batch writes to CSV (10 records per batch)
- Auto-updating Streamlit dashboard with metrics and charts
- API keys loaded from `.env` (not committed to git)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python |
| Data source | OpenWeatherMap API |
| Messaging | Apache Kafka (`kafka-python`) |
| Processing | pandas |
| Visualization | Streamlit, Plotly |
| Config | python-dotenv |

---

## Cities Tracked

New York, London, Tokyo, Delhi, Paris, Berlin, Sydney, Toronto, Dubai, Singapore

*(Edit the `CITIES` list in `producer.ipynb` to customize.)*

---

## Project Structure

```text
├── producer.ipynb      # Fetches weather data and publishes to Kafka
├── consumer.ipynb      # Consumes Kafka messages and appends batches to CSV
├── dashboard.py        # Streamlit app for live visualization
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template (copy to .env)
├── .gitignore
└── README.md
```

`weather_data.csv` is created at runtime by the consumer and is gitignored.

---

## Prerequisites

- Python 3.10+
- Apache Kafka running locally (`localhost:9092`)
- OpenWeatherMap API key ([sign up free](https://home.openweathermap.org/api_keys))

### Install Kafka (macOS)

```bash
brew install kafka
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Architgupta20/Weather-Data-Dashboard.git
cd Weather-Data-Dashboard
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set your API key:

```dotenv
OPENWEATHER_API_KEY=your_openweather_api_key_here
```

---

## Kafka Setup

Start Zookeeper and the Kafka broker (use two terminals):

```bash
zookeeper-server-start /opt/homebrew/etc/kafka/zookeeper.properties
```

```bash
kafka-server-start /opt/homebrew/etc/kafka/server.properties
```

> On Intel Macs with Homebrew, paths may be under `/usr/local/etc/kafka/` instead of `/opt/homebrew/etc/kafka/`.

Create the topic (only needed once):

```bash
kafka-topics --create \
  --topic weather_data \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

Verify the topic exists:

```bash
kafka-topics --list --bootstrap-server localhost:9092
```

---

## Run the Project

Run these from the project root with your virtual environment activated.

### Terminal 1 — Producer

Open `producer.ipynb` in Jupyter or VS Code and run all cells, **or**:

```bash
jupyter notebook producer.ipynb
```

The producer fetches weather for each city and publishes to the `weather_data` topic.

### Terminal 2 — Consumer

Open `consumer.ipynb` and run all cells. It listens on Kafka, collects 10 messages, appends them to `weather_data.csv`, then waits 30 seconds before the next batch.

### Terminal 3 — Dashboard

```bash
streamlit run dashboard.py
```

Open the URL shown in the terminal (typically **http://localhost:8501**). The dashboard reads `weather_data.csv` and refreshes every 30 seconds when new batches arrive.

---

## Data Schema

Each weather record contains:

| Field | Description |
|-------|-------------|
| `timestamp` | Unix timestamp from OpenWeatherMap |
| `city` | City name |
| `temperature` | Temperature (°C) |
| `humidity` | Humidity (%) |
| `wind_speed` | Wind speed (m/s) |
| `weather_condition` | Text description (e.g. clear sky) |

---

## Optional: Convert notebooks to scripts

```bash
jupyter nbconvert --to script producer.ipynb
jupyter nbconvert --to script consumer.ipynb
```

Then run `python producer.py` and `python consumer.py` instead of the notebooks.

---

## Author

**Archit Gupta**  
📧 [garchit1999@gmail.com](mailto:garchit1999@gmail.com)  
🔗 [LinkedIn](https://www.linkedin.com/in/archit-gupta-23ab7b1a3)
