import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import os

st.set_page_config(page_title="HFM Energy Saving Dashboard", layout="wide")
st_autorefresh(interval=5000, key="datarefresh")

AC1_KW = 1.2
AC2_KW = 1.2
UNIT_RATE = 55

try:
    DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception:
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL")


@st.cache_data(ttl=5)
def load_data():
    conn = psycopg2.connect(DATABASE_URL)
    df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp", conn)
    conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


df_all = load_data()

st.title("HFM Energy Saving Detection Dashboard")

if len(df_all) == 0:
    st.warning("Abhi koi data nahi hai. Pehle unified_system.py chalayein.")
    st.stop()

st.subheader("Live Status")
latest_per_room = df_all.sort_values("timestamp").groupby("room_name").tail(1)

live_cols = st.columns(len(latest_per_room))
for i, (_, row) in enumerate(latest_per_room.iterrows()):
    with live_cols[i]:
        any_ac_on = row["ac1_status"] == "ON" or row["ac2_status"] == "ON"
        is_waste = row["room_status"] == "EMPTY" and any_ac_on
        status_line = f"AC1: {row['ac1_status']} | AC2: {row['ac2_status']}"
        if is_waste:
            st.error(f"**{row['room_name']}**\n\nEMPTY + AC ON (Waste!)\n\n{status_line}")
        elif row["room_status"] == "OCCUPIED":
            st.success(f"**{row['room_name']}**\n\nOCCUPIED\n\n{status_line}")
        else:
            st.info(f"**{row['room_name']}**\n\nEMPTY\n\n{status_line}")
        st.caption(f"Last update: {row['timestamp'].strftime('%H:%M:%S')} | Phones: {row['phone_count']}")

st.divider()

rooms = sorted(df_all["room_name"].unique().tolist())
selected_room = st.selectbox("Room Select Karein (Detail View Ke Liye)", ["All Rooms"] + rooms)

if selected_room == "All Rooms":
    df = df_all.copy()
else:
    df = df_all[df_all["room_name"] == selected_room].copy()

st.caption(f"Data range: {df['timestamp'].min()} to {df['timestamp'].max()} | Records: {len(df)}")

total_alerts = int(df["alert_sent"].sum())
occupied_pct = (df["room_status"] == "OCCUPIED").mean() * 100 if len(df) > 0 else 0

if len(df) > 1:
    avg_gap_hours = (df["timestamp"].diff().dt.total_seconds().median() / 3600)
else:
    avg_gap_hours = 30 / 3600

waste_rows = df[df["room_status"] == "EMPTY"]
ac1_waste_hours = (waste_rows["ac1_status"] == "ON").sum() * avg_gap_hours
ac2_waste_hours = (waste_rows["ac2_status"] == "ON").sum() * avg_gap_hours

estimated_cost = (ac1_waste_hours * AC1_KW + ac2_waste_hours * AC2_KW) * UNIT_RATE
total_waste_hours = ac1_waste_hours + ac2_waste_hours

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Energy-Waste Alerts", total_alerts)
col2.metric("Room Occupancy %", f"{occupied_pct:.1f}%")
col3.metric("Estimated Wasted Hours (AC-hours)", f"{total_waste_hours:.2f} hrs")
col4.metric("Estimated Cost Wasted", f"Rs. {estimated_cost:,.0f}")

st.divider()

with st.expander("Detailed Charts (click to expand)", expanded=False):
    st.subheader("Room Occupancy Over Time")
    df["occupied_flag"] = (df["room_status"] == "OCCUPIED").astype(int)
    fig1 = px.line(df, x="timestamp", y="occupied_flag", color="room_name" if selected_room == "All Rooms" else None,
                   title="1 = Occupied, 0 = Empty")
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("AC1 vs AC2 Status Over Time")
    df["ac1_flag"] = (df["ac1_status"] == "ON").astype(int)
    df["ac2_flag"] = (df["ac2_status"] == "ON").astype(int)
    fig_ac = px.line(df, x="timestamp", y=["ac1_flag", "ac2_flag"], title="1 = ON, 0 = OFF")
    st.plotly_chart(fig_ac, use_container_width=True)

    st.subheader("Phone Usage Per Day")
    phone_by_day = df.groupby([df["timestamp"].dt.date, "room_name"])["phone_count"].sum().reset_index()
    phone_by_day.columns = ["date", "room_name", "phone_count"]
    fig3 = px.bar(phone_by_day, x="date", y="phone_count", color="room_name", barmode="group")
    st.plotly_chart(fig3, use_container_width=True)

with st.expander("Raw Data & Export", expanded=False):
    st.dataframe(df.sort_values("timestamp", ascending=False).head(100), use_container_width=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download Report (CSV)", csv, "hfm_energy_report.csv", "text/csv")