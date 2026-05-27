"""Spark Structured Streaming: Kafka -> Parquet lake + windowed aggregates + anomaly alerts."""

from __future__ import annotations

import pandas as pd
import pyspark
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from alerts import process_alerts
from anomaly_detector import detect_anomalies
from config import (
    AGGREGATES_PATH,
    CHECKPOINT_AGGREGATES,
    CHECKPOINT_EVENTS,
    EVENTS_PATH,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_STARTING_OFFSETS,
    KAFKA_TOPIC,
    SPARK_APP_NAME,
    TRIGGER_INTERVAL,
    WATERMARK_DELAY,
    WINDOW_DURATION,
)
from data_loader import load_events


WEATHER_SCHEMA = StructType(
    [
        StructField("timestamp", LongType(), False),
        StructField("city", StringType(), False),
        StructField("temperature", DoubleType(), True),
        StructField("humidity", DoubleType(), True),
        StructField("wind_speed", DoubleType(), True),
        StructField("weather_condition", StringType(), True),
    ]
)


def create_spark() -> SparkSession:
    spark_version = pyspark.__version__
    kafka_package = (
        f"org.apache.spark:spark-sql-kafka-0-10_2.12:{spark_version},"
        f"org.apache.spark:spark-token-provider-kafka-0-10_2.12:{spark_version}"
    )
    return (
        SparkSession.builder.appName(SPARK_APP_NAME)
        .master("local[*]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.jars.packages", kafka_package)
        .getOrCreate()
    )


def parse_kafka_stream(spark: SparkSession) -> DataFrame:
    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", KAFKA_STARTING_OFFSETS)
        .load()
    )

    parsed = raw.select(
        F.from_json(F.col("value").cast("string"), WEATHER_SCHEMA).alias("data")
    ).select("data.*")

    return (
        parsed.withColumn("event_time", F.from_unixtime("timestamp").cast(TimestampType()))
        .withColumn("event_date", F.to_date("event_time"))
        .withWatermark("event_time", WATERMARK_DELAY)
        .dropDuplicates(["city", "timestamp"])
        .dropna(subset=["city", "timestamp"])
    )


def process_batch(batch_df: DataFrame, batch_id: int) -> None:
    if batch_df.isEmpty():
        return

    rows = batch_df.collect()
    if not rows:
        return
    batch_pdf = pd.DataFrame([row.asDict() for row in rows])
    batch_pdf = batch_pdf.drop_duplicates(subset=["city", "timestamp"], keep="last")
    historical = load_events()
    alerts = detect_anomalies(batch_pdf, historical)

    enriched = (
        batch_df.withColumn("event_date", F.to_date("event_time"))
        .dropDuplicates(["city", "timestamp"])
    )
    (
        enriched.write.mode("append")
        .partitionBy("city", "event_date")
        .parquet(str(EVENTS_PATH))
    )
    sent = process_alerts(alerts)
    print(
        f"Batch {batch_id}: stored {len(batch_pdf)} events, "
        f"generated {len(alerts)} alerts, sent {sent} Slack notifications."
    )


def start_events_stream(parsed: DataFrame):
    EVENTS_PATH.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_EVENTS.mkdir(parents=True, exist_ok=True)

    return (
        parsed.writeStream.foreachBatch(process_batch)
        .option("checkpointLocation", str(CHECKPOINT_EVENTS))
        .trigger(processingTime=TRIGGER_INTERVAL)
        .start()
    )


def start_aggregate_stream(parsed: DataFrame):
    AGGREGATES_PATH.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_AGGREGATES.mkdir(parents=True, exist_ok=True)

    windowed = (
        parsed.groupBy(F.window(F.col("event_time"), WINDOW_DURATION), F.col("city"))
        .agg(
            F.avg("temperature").alias("avg_temperature"),
            F.avg("humidity").alias("avg_humidity"),
            F.avg("wind_speed").alias("avg_wind_speed"),
            F.count("*").alias("record_count"),
        )
        .select(
            "city",
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "avg_temperature",
            "avg_humidity",
            "avg_wind_speed",
            "record_count",
        )
    )

    return (
        windowed.writeStream.outputMode("append")
        .format("parquet")
        .option("path", str(AGGREGATES_PATH))
        .option("checkpointLocation", str(CHECKPOINT_AGGREGATES))
        .partitionBy("city")
        .trigger(processingTime=TRIGGER_INTERVAL)
        .start()
    )


def main() -> None:
    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")

    parsed = parse_kafka_stream(spark)
    events_query = start_events_stream(parsed)
    aggregates_query = start_aggregate_stream(parsed)

    print("Spark Structured Streaming started.")
    print(f"  Events path: {EVENTS_PATH}")
    print(f"  Aggregates path: {AGGREGATES_PATH}")
    print("Press Ctrl+C to stop.")

    try:
        spark.streams.awaitAnyTermination()
    finally:
        events_query.stop()
        aggregates_query.stop()
        spark.stop()


if __name__ == "__main__":
    main()
