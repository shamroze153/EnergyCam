import psycopg2
import time
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv

load_dotenv()

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
DATABASE_URL = os.getenv("DATABASE_URL")
DB_SSLMODE = os.getenv("DB_SSLMODE", "require")   # encrypted connection

CHECK_INTERVAL_SECONDS = 1800
MAX_SILENCE_HOURS = 2
PK_TZ = timezone(timedelta(hours=5), "PKT")   # display in Pakistan time


EXIT_CONFIG = 78   # same convention as unified_system.py; see run_system.bat


def check_config():
    """Stop with a clear message if a setting is missing, instead of crashing."""
    required = {
        "SENDER_EMAIL": SENDER_EMAIL,
        "APP_PASSWORD": APP_PASSWORD,
        "RECEIVER_EMAIL": RECEIVER_EMAIL,
        "DATABASE_URL": DATABASE_URL,
    }
    missing = [n for n, v in required.items() if not v or not str(v).strip()]
    if missing:
        print("")
        print(">> CONFIGURATION ERROR")
        print(">> Missing from .env: " + ", ".join(missing))
        print(">> The watchdog will not start until this is fixed.")
        raise SystemExit(EXIT_CONFIG)


def safe_error(e):
    """Exception type and standard code only: driver messages carry the host,
    port, user and database name. Mirrors unified_system.safe_error."""
    code = getattr(e, "pgcode", None) or getattr(e, "smtp_code", None)
    return type(e).__name__ + (" [%s]" % code if code else "")


def send_alert():
    msg = MIMEText("HFM System se pichle 2 ghante se koi heartbeat nahi aayi. System check karein — ho sakta hai band ho gaya ho.")
    msg["Subject"] = "WARNING: HFM System Down"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(">> Watchdog alert email sent.")
    except Exception as e:
        print(">> Watchdog email failed: %s" % safe_error(e))


def main():
    print("Watchdog chal raha hai... (Ctrl+C se rokein)")
    already_alerted = False

    while True:
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode=DB_SSLMODE)
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp FROM heartbeat ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                last_beat = row[0]
                if last_beat.tzinfo is not None:
                    now = datetime.now(last_beat.tzinfo)
                else:
                    now = datetime.now()
                silence = now - last_beat
                shown = last_beat.astimezone(PK_TZ) if last_beat.tzinfo is not None else last_beat
                print(f">> Last heartbeat: {shown:%Y-%m-%d %H:%M:%S} PKT, silence: {str(silence).split('.')[0]}")
                if silence > timedelta(hours=MAX_SILENCE_HOURS):
                    if not already_alerted:
                        send_alert()
                        already_alerted = True
                else:
                    already_alerted = False
            else:
                print(">> Abhi tak koi heartbeat nahi mili.")
        except Exception as e:
            print(">> Watchdog check error: %s" % safe_error(e))

        time.sleep(CHECK_INTERVAL_SECONDS)


# NOTE: never name this file watchdog.py - Streamlit imports the 'watchdog'
# package, would load this file instead and hang the dashboard forever.
if __name__ == "__main__":
    check_config()
    main()
