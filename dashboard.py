import streamlit as st
import pandas as pd
import plotly.express as px
import time

st.set_page_config(layout="wide")

# Initialize session state variables
if "start_index" not in st.session_state:
    st.session_state.start_index = 0  # Track the current 10-record batch
if "refresh_count" not in st.session_state:
    st.session_state.refresh_count = 0  # Count dashboard refreshes

# File path
DATA_FILE = "weather_data.csv"

# Function to load data
@st.cache_data(ttl=10)
def load_data():
    try:
        df = pd.read_csv(DATA_FILE)
        if df.empty:
            return pd.DataFrame()  # Return empty DataFrame if no data
        return df
    except:
        return pd.DataFrame()

# Create placeholders
refresh_placeholder = st.empty()
data_placeholder = st.empty()
metrics_placeholder = st.empty()
chart_placeholder = st.empty()

while True:
    df = load_data()

    if not df.empty:
        total_rows = len(df)

        # If new 10 records are available, update the display
        if st.session_state.start_index + 10 <= total_rows:
            df_display = df.iloc[st.session_state.start_index : st.session_state.start_index + 10]  # Take next 10 records
            st.session_state.start_index += 10  # Move to next batch
            st.session_state.refresh_count += 1  # Increase refresh count

            # Display refresh count
            with refresh_placeholder.container():
                st.success(f"🔄 Dashboard refreshed {st.session_state.refresh_count} time(s)")

            # Display Data
            with data_placeholder.container():
                st.subheader("Latest Weather Data (Entries in Order of Arrival)")
                st.dataframe(df_display)

            # Display Metrics
            with metrics_placeholder.container():
                col1, col2, col3 = st.columns(3)
                col1.metric("Avg Temp (°C)", round(df_display["temperature"].mean(), 2))
                col2.metric("Avg Humidity (%)", round(df_display["humidity"].mean(), 2))
                col3.metric("Avg Wind Speed (km/h)", round(df_display["wind_speed"].mean(), 2))

            # Display Charts
            with chart_placeholder.container():
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("📈 Temperature Trends")
                    fig_temp = px.line(df_display, x="timestamp", y="temperature", color="city",
                                       markers=True, title="Temperature Trends")
                    st.plotly_chart(fig_temp, use_container_width=True, key=f"temp_{st.session_state.refresh_count}")

                with col2:
                    st.subheader("🏙️ City-wise Weather Conditions")
                    city_weather = df_display.groupby("city")["weather_condition"].value_counts().unstack().fillna(0)
                    fig_weather = px.bar(city_weather, title="City-wise Weather Conditions", barmode="stack")
                    st.plotly_chart(fig_weather, use_container_width=True, key=f"weather_{st.session_state.refresh_count}")

                col3, col4 = st.columns(2)

                with col3:
                    st.subheader("💧 Humidity Distribution")
                    fig_humidity = px.pie(df_display, names="city", values="humidity", title="Humidity Distribution by City")
                    st.plotly_chart(fig_humidity, use_container_width=True, key=f"humidity_{st.session_state.refresh_count}")

                with col4:
                    st.subheader("💨 Wind Speed vs. Temperature")
                    fig_scatter = px.scatter(df_display, x="wind_speed", y="temperature", color="city",
                                             size="humidity", hover_data=["weather_condition"],
                                             title="Wind Speed vs Temperature")
                    st.plotly_chart(fig_scatter, use_container_width=True, key=f"scatter_{st.session_state.refresh_count}")

                # Additional Visualization 1: Bar Chart for City-wise Average Temperature
                st.subheader("🌡️ City-wise Average Temperature")
                avg_temp = df_display.groupby("city")["temperature"].mean().reset_index()
                fig_avg_temp = px.bar(avg_temp, x="city", y="temperature", title="Average Temperature per City",
                                      color="temperature", color_continuous_scale="bluered")
                st.plotly_chart(fig_avg_temp, use_container_width=True, key=f"avg_temp_{st.session_state.refresh_count}")

                # Additional Visualization 2: Heatmap for Temperature vs. Humidity with "ice" color
                st.subheader("🔥 Heatmap: Temperature vs. Humidity")
                fig_heatmap = px.density_heatmap(df_display, x="temperature", y="humidity",
                                                 color_continuous_scale="ice", title="Temperature vs. Humidity Heatmap")
                st.plotly_chart(fig_heatmap, use_container_width=True, key=f"heatmap_{st.session_state.refresh_count}")

    time.sleep(30)  # Wait 30 seconds before checking again