import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

AC1_KW = 1.2
AC2_KW = 1.2
UNIT_RATE = 55

conn = psycopg2.connect(DATABASE_URL)
df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp", conn)
conn.close()
df["timestamp"] = pd.to_datetime(df["timestamp"])

if len(df) == 0:
    print("Abhi koi data nahi hai. Pehle unified_system.py chalayein.")
    exit()

date_from = df["timestamp"].min().strftime("%d-%b-%Y %H:%M")
date_to = df["timestamp"].max().strftime("%d-%b-%Y %H:%M")

if len(df) > 1:
    gap_hours = df["timestamp"].diff().dt.total_seconds().median() / 3600
else:
    gap_hours = 30 / 3600

total_alerts = int(df["alert_sent"].sum())
occupied_pct = (df["room_status"] == "OCCUPIED").mean() * 100

waste_rows = df[df["room_status"] == "EMPTY"]
ac1_waste_hours = (waste_rows["ac1_status"] == "ON").sum() * gap_hours
ac2_waste_hours = (waste_rows["ac2_status"] == "ON").sum() * gap_hours
total_waste_hours = ac1_waste_hours + ac2_waste_hours
estimated_cost = (ac1_waste_hours * AC1_KW + ac2_waste_hours * AC2_KW) * UNIT_RATE

df["date"] = df["timestamp"].dt.date
waste_condition = (df["room_status"] == "EMPTY") & ((df["ac1_status"] == "ON") | (df["ac2_status"] == "ON"))
daily_waste = df[waste_condition].groupby(df["date"]).size()

plt.figure(figsize=(7, 3))
if len(daily_waste) > 0:
    daily_waste.plot(kind="bar", color="#d9534f")
else:
    plt.text(0.5, 0.5, "Is period mein koi waste incident nahi mila", ha="center", va="center")
plt.title("Energy Waste Incidents Per Day")
plt.ylabel("Log entries (empty + AC on)")
plt.tight_layout()
plt.savefig("waste_chart.png", dpi=150)
plt.close()

pdf = FPDF()
pdf.add_page()

pdf.set_font("Helvetica", "B", 18)
pdf.cell(0, 12, "HFM Energy Saving Detection Report", ln=True, align="C")

pdf.set_font("Helvetica", "", 11)
rooms_covered = ", ".join(sorted(df["room_name"].unique().tolist()))
pdf.cell(0, 8, f"Room(s): {rooms_covered}", ln=True, align="C")
pdf.cell(0, 8, f"Period: {date_from} to {date_to}", ln=True, align="C")
pdf.cell(0, 8, f"Generated on: {datetime.now().strftime('%d-%b-%Y %H:%M')}", ln=True, align="C")
pdf.ln(8)

pdf.set_font("Helvetica", "B", 13)
pdf.cell(0, 10, "Summary", ln=True)
pdf.set_font("Helvetica", "", 11)

rows = [
    ("Total Energy-Waste Alerts", str(total_alerts)),
    ("Room Occupancy %", f"{occupied_pct:.1f}%"),
    ("Estimated Wasted Hours (AC-hours)", f"{total_waste_hours:.1f} hrs"),
    ("Estimated Cost Wasted", f"Rs. {estimated_cost:,.0f}"),
    ("Total Log Records", str(len(df))),
]

for label, value in rows:
    pdf.cell(100, 9, label, border=1)
    pdf.cell(80, 9, value, border=1, ln=True)

pdf.ln(8)
pdf.set_font("Helvetica", "B", 13)
pdf.cell(0, 10, "Energy Waste Incidents (Daily Trend)", ln=True)
pdf.image("waste_chart.png", w=180)

pdf.ln(5)
pdf.set_font("Helvetica", "I", 9)
pdf.multi_cell(0, 6, "Note: This report is based on AI camera detection (person presence + AC LED/flap sensing). Cost estimates use AC power rating of 1.2 kW per unit and a unit rate of Rs. 55/kWh - adjust in script if these change.")

output_path = "HFM_Energy_Report.pdf"
pdf.output(output_path)
print(f"Report ban gayi: {output_path}")