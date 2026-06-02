"""Short-horizon weather forecasting for dashboard visualization."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_HISTORY_POINTS = 12
DEFAULT_FREQ = "30min"


@dataclass
class ForecastResult:
    method: str
    history: pd.DataFrame
    forecast: pd.DataFrame
    holdout_actual: pd.DataFrame
    holdout_predicted: pd.DataFrame
    mae: float | None
    rmse: float | None
    message: str


def prepare_city_series(
    events: pd.DataFrame,
    city: str,
    metric: str,
    freq: str = DEFAULT_FREQ,
) -> pd.Series:
    """Resample city metric to a regular time series."""
    if events.empty or "city" not in events.columns or metric not in events.columns:
        return pd.Series(dtype=float)

    city_df = events[events["city"] == city].copy()
    if city_df.empty:
        return pd.Series(dtype=float)

    if "event_time" in city_df.columns:
        city_df["event_time"] = pd.to_datetime(city_df["event_time"], utc=True)
        city_df = city_df.set_index("event_time")
    else:
        city_df["event_time"] = pd.to_datetime(city_df["timestamp"], unit="s", utc=True)
        city_df = city_df.set_index("event_time")

    series = (
        city_df[metric]
        .astype(float)
        .sort_index()
        .resample(freq)
        .mean()
        .interpolate(method="time")
        .dropna()
    )
    return series


def _infer_freq(series: pd.Series) -> str:
    if len(series) < 2:
        return DEFAULT_FREQ
    deltas = series.index.to_series().diff().dropna()
    if deltas.empty:
        return DEFAULT_FREQ
    median_seconds = int(deltas.median().total_seconds())
    if median_seconds <= 90:
        return "1min"
    if median_seconds <= 600:
        return "5min"
    if median_seconds <= 2100:
        return "30min"
    return "1H"


def _series_to_prophet_df(series: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({"ds": series.index.tz_convert(None), "y": series.values})


def _forecast_prophet(series: pd.Series, periods: int, freq: str) -> pd.DataFrame:
    from prophet import Prophet

    train = _series_to_prophet_df(series)
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=False,
        yearly_seasonality=False,
    )
    model.fit(train)
    future = model.make_future_dataframe(periods=periods, freq=freq)
    predicted = model.predict(future)
    forecast_rows = predicted.tail(periods)
    return pd.DataFrame(
        {
            "ds": pd.to_datetime(forecast_rows["ds"], utc=True),
            "yhat": forecast_rows["yhat"].values,
            "yhat_lower": forecast_rows["yhat_lower"].values,
            "yhat_upper": forecast_rows["yhat_upper"].values,
        }
    )


def _forecast_statsmodels(series: pd.Series, periods: int) -> pd.DataFrame:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    model = ExponentialSmoothing(series.values, trend="add", seasonal=None)
    fit = model.fit(optimized=True)
    preds = fit.forecast(periods)

    last_ts = series.index[-1]
    freq = pd.infer_freq(series.index) or DEFAULT_FREQ
    future_index = pd.date_range(start=last_ts, periods=periods + 1, freq=freq)[1:]

    std = float(np.std(series.values)) if len(series) > 1 else 1.0
    margin = max(std * 0.5, 0.5)
    return pd.DataFrame(
        {
            "ds": future_index,
            "yhat": preds,
            "yhat_lower": preds - margin,
            "yhat_upper": preds + margin,
        }
    )


def _forecast_linear(series: pd.Series, periods: int) -> pd.DataFrame:
    """Fallback linear trend when data or libraries are limited."""
    y = series.values.astype(float)
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    future_x = np.arange(len(y), len(y) + periods)
    preds = slope * future_x + intercept

    last_ts = series.index[-1]
    freq = pd.infer_freq(series.index) or DEFAULT_FREQ
    future_index = pd.date_range(start=last_ts, periods=periods + 1, freq=freq)[1:]

    std = float(np.std(y)) if len(y) > 1 else 1.0
    margin = max(std * 0.5, 0.5)
    return pd.DataFrame(
        {
            "ds": future_index,
            "yhat": preds,
            "yhat_lower": preds - margin,
            "yhat_upper": preds + margin,
        }
    )


def _run_holdout_backtest(series: pd.Series, periods: int, method: str, freq: str) -> tuple[pd.DataFrame, pd.DataFrame, float | None, float | None]:
    holdout_size = max(2, min(periods, len(series) // 4))
    if len(series) <= holdout_size + MIN_HISTORY_POINTS:
        return pd.DataFrame(), pd.DataFrame(), None, None

    train = series.iloc[:-holdout_size]
    test = series.iloc[-holdout_size:]
    try:
        if method == "prophet":
            predicted = _forecast_prophet(train, holdout_size, freq)
        elif method == "exponential_smoothing":
            predicted = _forecast_statsmodels(train, holdout_size)
        else:
            predicted = _forecast_linear(train, holdout_size)
    except Exception:
        return pd.DataFrame(), pd.DataFrame(), None, None

    predicted = predicted.set_index("ds")["yhat"].reindex(test.index)
    valid = ~(predicted.isna() | test.isna())
    if not valid.any():
        return pd.DataFrame(), pd.DataFrame(), None, None

    actual = test[valid]
    pred = predicted[valid]
    mae = float(np.mean(np.abs(actual - pred)))
    rmse = float(np.sqrt(np.mean((actual - pred) ** 2)))
    return (
        pd.DataFrame({"ds": actual.index, "y": actual.values}),
        pd.DataFrame({"ds": pred.index, "yhat": pred.values}),
        mae,
        rmse,
    )


def _forecast_with_method(series: pd.Series, periods: int, freq: str, method: str) -> pd.DataFrame:
    if method == "prophet":
        return _forecast_prophet(series, periods, freq)
    if method == "exponential_smoothing":
        return _forecast_statsmodels(series, periods)
    if method == "linear_trend":
        return _forecast_linear(series, periods)
    raise ValueError(f"Unknown forecast method: {method}")


def _auto_forecast(series: pd.Series, periods: int, freq: str) -> tuple[pd.DataFrame, str]:
    try:
        return _forecast_prophet(series, periods, freq), "prophet"
    except ImportError:
        pass
    except Exception:
        pass
    try:
        return _forecast_statsmodels(series, periods), "exponential_smoothing"
    except Exception:
        pass
    return _forecast_linear(series, periods), "linear_trend"


def generate_forecast(
    events: pd.DataFrame,
    city: str,
    metric: str,
    periods: int = 6,
    method_preference: str = "auto",
) -> ForecastResult:
    """Build forecast; use method_preference or auto cascade (Prophet → ETS → linear)."""
    series = prepare_city_series(events, city, metric)
    if len(series) < MIN_HISTORY_POINTS:
        return ForecastResult(
            method="none",
            history=pd.DataFrame(),
            forecast=pd.DataFrame(),
            holdout_actual=pd.DataFrame(),
            holdout_predicted=pd.DataFrame(),
            mae=None,
            rmse=None,
            message=(
                f"Need at least {MIN_HISTORY_POINTS} points for {city}. "
                "Keep the pipeline running to collect more history."
            ),
        )

    freq = _infer_freq(series)

    if method_preference == "auto":
        forecast_df, method = _auto_forecast(series, periods, freq)
    else:
        try:
            forecast_df = _forecast_with_method(series, periods, freq, method_preference)
            method = method_preference
        except Exception as exc:
            return ForecastResult(
                method="none",
                history=pd.DataFrame(),
                forecast=pd.DataFrame(),
                holdout_actual=pd.DataFrame(),
                holdout_predicted=pd.DataFrame(),
                mae=None,
                rmse=None,
                message=f"Could not run {method_preference.replace('_', ' ')}: {exc}",
            )

    history_df = pd.DataFrame({"ds": series.index, "y": series.values})
    holdout_actual, holdout_predicted, mae, rmse = _run_holdout_backtest(series, periods, method, freq)

    return ForecastResult(
        method=method,
        history=history_df,
        forecast=forecast_df,
        holdout_actual=holdout_actual,
        holdout_predicted=holdout_predicted,
        mae=mae,
        rmse=rmse,
        message="Forecast generated successfully.",
    )
