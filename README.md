# 🌦 Real-Time Weather Data Analytics Dashboard

This project is a **real-time weather data analytics system** that fetches live data from the **OpenWeatherMap API**, streams it using **Apache Kafka**, processes it with **Apache Spark Structured Streaming**, and visualizes live insights using an interactive **Dash (Plotly) dashboard**.

---

## 🚀 Features

- Live weather data from 10 global cities.
- Real-time data streaming using Apache Kafka.
- Spark Structured Streaming-based consumer and CSV writer.
- Automatically updating Dash dashboard.
- Modular Python codebase.
- Ready for local or cloud deployment.

---

## 🛠️ Tech Stack

- **Programming Language**: Python
- **Streaming Engine**: Apache Kafka
- **Data Processing**: Apache Spark (Structured Streaming)
- **Visualization**: Dash (Plotly)
- **Data Source**: OpenWeatherMap API
- **IDE**: Visual Studio Code

---

## 🌍 Cities Tracked

- Delhi
- Mumbai
- New York
- London
- Paris
- Tokyo
- Sydney
- Cape Town
- Dubai
- Toronto

*(Feel free to customize this list in the code)*

---

## 📁 Project Structure

weather-dashboard/
│
├── producer.py # Fetches weather data from API and streams to Kafka
├── consumer.py # Consumes Kafka data and writes to weather_data.csv
├── dashboard.py # Dash app to visualize real-time weather insights
├── weather_data.csv # Auto-updated file storing live weather data
├── requirements.txt # Python dependencies
├── .env # Stores API keys and configs (add this to .gitignore)
└── README.md # Project documentation


---

## ⚙️ Setup Instructions (MacBook & VS Code)

### 1. 🧱 Install Prerequisites

```bash
brew install kafka
brew install apache-spark
pip install virtualenv

cd weather-dashboard
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
kafka-python
dash
pandas
requests
pyspark
API_KEY=your_openweather_api_key


# Start Zookeeper
zookeeper-server-start /usr/local/etc/kafka/zookeeper.properties

# In a new terminal, start Kafka broker
kafka-server-start /usr/local/etc/kafka/server.properties

# Create Kafka topic
kafka-topics --create --topic weather_topic --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
