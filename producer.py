"""Stream live OpenWeatherMap data to Kafka."""

import json
import os
import time

import requests
from dotenv import load_dotenv
from kafka import KafkaProducer

from config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not API_KEY:
    raise ValueError(
        "OPENWEATHER_API_KEY is not set. Copy .env.example to .env and add your API key."
    )

CITIES = [
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

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    key_serializer=lambda key: key.encode("utf-8"),
    value_serializer=lambda payload: json.dumps(payload).encode("utf-8"),
    acks="all",
    retries=10,
)


def fetch_weather(city: str) -> dict | None:
    url = (
        "http://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={API_KEY}&units=metric"
    )
    response = requests.get(url, timeout=15)
    if response.status_code != 200:
        print(f"Error for {city}: {response.status_code} - {response.text}")
        return None

    weather_data = response.json()
    return {
        "timestamp": weather_data["dt"],
        "city": weather_data["name"],
        "temperature": weather_data["main"]["temp"],
        "humidity": weather_data["main"]["humidity"],
        "wind_speed": weather_data["wind"]["speed"],
        "weather_condition": weather_data["weather"][0]["description"],
    }


def main() -> None:
    print(f"Publishing to Kafka topic '{KAFKA_TOPIC}' at {KAFKA_BOOTSTRAP_SERVERS}")
    while True:
        for city in CITIES:
            record = fetch_weather(city)
            if record:
                record_key = f"{record['city']}:{record['timestamp']}"
                producer.send(KAFKA_TOPIC, key=record_key, value=record)
                print(f"Sent: {record}")
            time.sleep(2)

        print("Waiting 30 seconds before the next round...")
        time.sleep(30)


if __name__ == "__main__":
    main()
