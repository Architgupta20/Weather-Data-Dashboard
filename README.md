# ⛅ Real-Time Weather Data Dashboard

A real-time data analytics platform that fetches live weather data from the OpenWeatherMap API, streams it using **Apache Kafka**, processes it using **Apache Spark Structured Streaming**, and visualizes meaningful insights with a live-updating **Dash (Plotly) dashboard**.

---

## 🔧 Features

- Streams live weather data for 10 cities using OpenWeatherMap API
- Real-time data pipeline using Kafka Producer and Consumer
- Spark Structured Streaming used to process incoming weather data
- CSV file (`weather_data.csv`) updated live by Spark Consumer
- Dash (Plotly) dashboard that dynamically displays weather insights
- Modular, well-structured codebase
- Built and tested on **macOS**, using **Visual Studio Code**

---

## 📁 Project Structure

```plaintext
weather-dashboard/
├── producer.ipynb        # Jupyter notebook to stream live weather data to Kafka
├── consumer.ipynb        # Jupyter notebook to consume data and store to CSV
├── dashboard.py          # Dash app that visualizes real-time weather insights
├── requirements.txt      # Python dependencies
├── .gitignore            # Ignored files
└── README.md             # Project documentation
```

---

## ⚙️ Setup Instructions

### 1. Clone Repository

```bash
git clone https://github.com/architgupta280/Weather-Data-Dashboard.git
cd Weather-Data-Dashboard
```

### 2. Create & Activate Virtual Environment (macOS)

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔌 Apache Kafka & Spark Setup

> Make sure Kafka and Spark are installed and configured on your system.

### Start Zookeeper and Kafka Server

```bash
zookeeper-server-start /usr/local/etc/kafka/zookeeper.properties
kafka-server-start /usr/local/etc/kafka/server.properties
```

### Create Kafka Topic

```bash
kafka-topics --create \
--bootstrap-server localhost:9092 \
--replication-factor 1 \
--partitions 1 \
--topic weather_topic
```

---

## 🚀 Run the Project

### 1. Run Kafka Producer (from notebook or convert to `.py`)

```bash
# Inside producer.ipynb or equivalent .py
python producer.py
```

### 2. Run Spark Kafka Consumer

```bash
# Inside consumer.ipynb or equivalent .py
python consumer.py
```

### 3. Launch Dash Dashboard

```bash
python dashboard.py
```

Then go to `http://127.0.0.1:8050` in your browser.

---

## 📝 .gitignore

```txt
__pycache__/
*.pyc
*.env
venv/
weather_data.csv
.ipynb_checkpoints/
.DS_Store
```

---

## 📦 requirements.txt

```txt
dash
kafka-python
pyspark
pandas
requests
python-dotenv
```

---

## 📌 Notes

- You must create a **`.env`** file with your OpenWeatherMap API key:
  
```dotenv
API_KEY=your_api_key_here
```

- You can convert your `.ipynb` files to `.py` for smoother execution using:
  
```bash
jupyter nbconvert --to script producer.ipynb
jupyter nbconvert --to script consumer.ipynb
```

---

## 🙋‍♂️ Author

**Archit Gupta**  
📧 [Email](mailto:your-email@example.com) | 🌐 [LinkedIn](https://www.linkedin.com/in/architgupta280/)  
🚀 Built with love for real-time data and clean dashboards.

---
