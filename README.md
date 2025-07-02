# ⛅ Real-Time Weather Data Dashboard

A real-time weather data analytics platform that streams live data from the OpenWeatherMap API using **Apache Kafka**, processes it using **Apache Spark Structured Streaming**, and visualizes live insights using an interactive **Dash (Plotly) dashboard**.

---

## 🔧 Features

- Streams **real-time weather data** from OpenWeatherMap API
- Covers **10 major cities**
- Uses **Kafka + Spark Structured Streaming**
- Auto-updating **Dash dashboard**
- Modular Python codebase

---

## 📁 Project Structure

```plaintext
weather-dashboard/
├── producer.py
├── consumer.py
├── dashboard.py
├── requirements.txt
├── .gitignore
└── README.md

⚙️ Setup Instructions
# Clone the repo
git clone https://github.com/architgupta280/Weather-Data-Dashboard.git
cd Weather-Data-Dashboard

# Initialize git
git init

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
