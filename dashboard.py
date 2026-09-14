import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import psycopg2
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import os

st.set_page_config(page_title="HFM Energy Saving Dashboard", layout="wide", page_icon="❄️")
st_autorefresh(interval=5000, key="datarefresh")

AC1_KW = 1.2
AC2_KW = 1.2
UNIT_RATE = 55
CO2_FACTOR_KG_PER_KWH = 0.45

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


def get_room_metrics(df_all, room_name, ac1_kw, ac2_kw, unit_rate):
    df_room = df_all[df_all["room_name"] == room_name].sort_values("timestamp").reset_index(drop=True)
    latest = df_room.iloc[-1]
    any_ac_on = latest["ac1_status"] == "ON" or latest["ac2_status"] == "ON"
    is_waste = latest["room_status"] == "EMPTY" and any_ac_on

    cond_all = (df_room["room_status"] == "EMPTY") & ((df_room["ac1_status"] == "ON") | (df_room["ac2_status"] == "ON"))

    current_waste_seconds = 0
    if is_waste:
        false_idxs = df_room.index[~cond_all]
        prior_false = false_idxs[false_idxs < df_room.index[-1]]
        start_idx = (prior_false[-1] + 1) if len(prior_false) > 0 else 0
        waste_start_time = df_room.loc[start_idx, "timestamp"]
        current_waste_seconds = (latest["timestamp"] - waste_start_time).total_seconds()

    waste_rows = df_room[cond_all]
    if is_waste:
        streak_days = 0
    elif len(waste_rows) > 0:
        streak_days = (latest["timestamp"] - waste_rows["timestamp"].max()).days
    else:
        streak_days = (latest["timestamp"] - df_room["timestamp"].min()).days

    if len(df_room) > 1:
        gap_hours = df_room["timestamp"].diff().dt.total_seconds().median() / 3600
    else:
        gap_hours = 30 / 3600

    df_room["month"] = df_room["timestamp"].dt.to_period("M")
    waste_by_month = df_room[cond_all].groupby("month").apply(
        lambda g: ((g["ac1_status"] == "ON").sum() * ac1_kw + (g["ac2_status"] == "ON").sum() * ac2_kw) * gap_hours * unit_rate
    )
    months_sorted = sorted(waste_by_month.index) if len(waste_by_month) > 0 else []
    this_month_cost = float(waste_by_month.get(months_sorted[-1], 0)) if months_sorted else 0.0
    last_month_cost = float(waste_by_month.get(months_sorted[-2], 0)) if len(months_sorted) > 1 else None

    person_count_val = latest["person_count"] if "person_count" in df_room.columns else 0
    if pd.isna(person_count_val):
        person_count_val = 0

    return {
        "is_waste": is_waste,
        "room_status": latest["room_status"],
        "ac1_status": latest["ac1_status"],
        "ac2_status": latest["ac2_status"],
        "person_count": int(person_count_val),
        "current_waste_seconds": current_waste_seconds,
        "streak_days": streak_days,
        "this_month_cost": this_month_cost,
        "last_month_cost": last_month_cost,
        "last_updated": latest["timestamp"],
    }


def render_room_card(room_name, m, ac1_kw, ac2_kw, unit_rate):
    is_waste = m["is_waste"]
    active_kw = 0.0
    if m["ac1_status"] == "ON":
        active_kw += ac1_kw
    if m["ac2_status"] == "ON":
        active_kw += ac2_kw
    rate_per_sec = (active_kw * unit_rate) / 3600
    seconds = int(m["current_waste_seconds"])

    if is_waste:
        pill_text = "Empty, AC on"
        pill_bg, pill_color = "#FCEBEB", "#A32D2D"
    elif m["room_status"] == "OCCUPIED":
        pill_text = "Occupied"
        pill_bg, pill_color = "#EAF3DE", "#3B6D11"
    else:
        pill_text = "Empty, AC off"
        pill_bg, pill_color = "#FAEEDA", "#854F0B"

    last_updated_str = m["last_updated"].strftime("%H:%M:%S")

    if m["last_month_cost"] is not None:
        compare_html = f"""
        <div style="border-top: 1px solid #eee; padding-top: 12px; margin-bottom: 12px;">
          <p style="font-size: 12px; color: #888; margin: 0 0 8px;">This month vs last month (actual waste cost)</p>
          <div style="display: flex; align-items: flex-end; gap: 16px; height: 60px;">
            <div style="flex:1; text-align:center;">
              <p style="font-size: 12px; color: #888; margin: 0;">Last month</p>
              <p style="font-size: 15px; font-weight: 600; margin: 2px 0 0; color:#333;">Rs {m['last_month_cost']:,.0f}</p>
            </div>
            <div style="flex:1; text-align:center;">
              <p style="font-size: 12px; color: #888; margin: 0;">This month</p>
              <p style="font-size: 15px; font-weight: 600; margin: 2px 0 0; color:#333;">Rs {m['this_month_cost']:,.0f}</p>
            </div>
          </div>
        </div>
        """
    else:
        compare_html = ""

    html = f"""
    <div id="card-{room_name}" style="font-family: -apple-system, 'Segoe UI', sans-serif; background: #fff; border-radius: 14px; border: 1px solid #e8e8e8; box-shadow: 0 2px 10px rgba(0,0,0,0.05); padding: 1.25rem; max-width: 420px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
        <p style="font-weight: 700; font-size: 17px; margin: 0; color:#1a1a1a;">{room_name}</p>
        <span style="background: {pill_bg}; color: {pill_color}; font-size: 12px; font-weight: 600; padding: 4px 11px; border-radius: 20px;">{pill_text}</span>
      </div>
      <p style="font-size: 11px; color: #aaa; margin: 0 0 14px;">Last updated {last_updated_str}</p>

      <div style="background: linear-gradient(135deg, #f9f9f8, #f2f2f0); border-radius: 10px; padding: 14px; text-align: center; margin-bottom: 12px;">
        <p style="font-size: 12px; color: #888; margin: 0;">Wasting energy for</p>
        <p id="timer-{room_name}" style="font-size: 30px; font-weight: 700; margin: 4px 0 0; color:#1a1a1a; font-variant-numeric: tabular-nums;">00:00:00</p>
      </div>

      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px;">
        <div style="background: #f7f7f5; border-radius: 10px; padding: 10px; text-align: center;">
          <p style="font-size: 17px; margin: 0;">👥</p>
          <p style="font-size: 11px; color: #888; margin: 2px 0 0;">People</p>
          <p style="font-size: 14px; font-weight: 700; margin: 1px 0 0; color:#333;">{m['person_count']}</p>
        </div>
        <div style="background: #f7f7f5; border-radius: 10px; padding: 10px; text-align: center;">
          <p style="font-size: 17px; margin: 0;">❄️</p>
          <p style="font-size: 11px; color: #888; margin: 2px 0 0;">AC1</p>
          <p style="font-size: 14px; font-weight: 700; margin: 1px 0 0; color:{'#A32D2D' if m['ac1_status']=='ON' else '#333'};">{m['ac1_status']}</p>
        </div>
        <div style="background: #f7f7f5; border-radius: 10px; padding: 10px; text-align: center;">
          <p style="font-size: 17px; margin: 0;">❄️</p>
          <p style="font-size: 11px; color: #888; margin: 2px 0 0;">AC2</p>
          <p style="font-size: 14px; font-weight: 700; margin: 1px 0 0; color:{'#A32D2D' if m['ac2_status']=='ON' else '#333'};">{m['ac2_status']}</p>
        </div>
      </div>

      <div style="background: #EAF3DE; border-radius: 10px; padding: 9px 13px; margin-bottom: 12px; display:flex; align-items:center; gap:8px;">
        <span style="font-size:14px;">🔥</span>
        <p style="font-size: 13px; color: #3B6D11; margin: 0; font-weight: 500;">{m['streak_days']}-day waste-free streak</p>
      </div>

      {compare_html}

      <div style="display:flex; justify-content:space-between; align-items:baseline;">
        <p style="font-size: 12px; color: #888; margin: 0;">Cost ticking now</p>
        <p id="cost-{room_name}" style="font-size: 19px; font-weight: 700; margin: 0; color:#A32D2D;">Rs 0.00</p>
      </div>
    </div>
    <script>
    (function() {{
      let seconds = {seconds};
      const rate = {rate_per_sec};
      const isWaste = {str(is_waste).lower()};
      function fmt(s) {{
        const h = String(Math.floor(s/3600)).padStart(2,'0');
        const m = String(Math.floor((s%3600)/60)).padStart(2,'0');
        const sec = String(s%60).padStart(2,'0');
        return h+':'+m+':'+sec;
      }}
      document.getElementById('timer-{room_name}').textContent = fmt(seconds);
      document.getElementById('cost-{room_name}').textContent = 'Rs ' + (seconds*rate).toFixed(2);
      if (isWaste) {{
        setInterval(() => {{
          seconds += 1;
          document.getElementById('timer-{room_name}').textContent = fmt(seconds);
          document.getElementById('cost-{room_name}').textContent = 'Rs ' + (seconds*rate).toFixed(2);
        }}, 1000);
      }}
    }})();
    </script>
    """
    components.html(html, height=470 if compare_html else 370)


df_all = load_data()

st.markdown("""
<div style="background: linear-gradient(90deg, #1a3c34, #2d5a4f); border-radius: 14px; padding: 24px 30px; margin-bottom: 8px;">
  <p style="color: #fff; font-size: 26px; font-weight: 700; margin: 0;">❄️ HFM Energy Saving Detection</p>
  <p style="color: #d0e0da; font-size: 14px; margin: 4px 0 0;">Real-time occupancy & AC monitoring — powered by computer vision</p>
</div>
""", unsafe_allow_html=True)

if len(df_all) == 0:
    st.warning("Abhi koi data nahi hai. Pehle unified_system.py chalayein.")
    st.stop()

st.subheader("Live Status")
rooms = sorted(df_all["room_name"].unique().tolist())
live_cols = st.columns(len(rooms))
for i, room_name in enumerate(rooms):
    with live_cols[i]:
        metrics = get_room_metrics(df_all, room_name, AC1_KW, AC2_KW, UNIT_RATE)
        render_room_card(room_name, metrics, AC1_KW, AC2_KW, UNIT_RATE)

st.divider()

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
total_waste_kwh = ac1_waste_hours * AC1_KW + ac2_waste_hours * AC2_KW
co2_saved_kg = total_waste_kwh * CO2_FACTOR_KG_PER_KWH

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Energy-Waste Alerts", total_alerts)
col2.metric("Room Occupancy %", f"{occupied_pct:.1f}%")
col3.metric("Estimated Wasted Hours (AC-hours)", f"{total_waste_hours:.2f} hrs")
col4.metric("Estimated Cost Wasted", f"Rs. {estimated_cost:,.0f}")
col5.metric("CO2 Impact", f"{co2_saved_kg:.1f} kg")

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