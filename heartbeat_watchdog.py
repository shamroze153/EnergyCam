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

# The loop beats once a minute now, not once every five, and the thing it
# is watching runs unattended overnight. Two hours of silence used to be a
# reasonable alarm; it is now two hours of night nobody recorded, which is
# the part of the day this whole system exists to measure. Twenty minutes is
# late enough to ride out a restart and early enough that somebody can still
# do something about it.
CHECK_INTERVAL_SECONDS = 300
MAX_SILENCE_MINUTES = 20
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


def spell(gap):
    if gap is None:
        return "an unknown time"
    minutes = int(gap.total_seconds() // 60)
    if minutes < 60:
        return "%d minutes" % minutes
    hours, rest = divmod(minutes, 60)
    return "%dh" % hours if not rest else "%dh %02dm" % (hours, rest)


def send(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.send_message(msg)
        print(">> sent: %s" % subject)
    except Exception as e:                                  # noqa: BLE001
        print(">> Watchdog email failed: %s" % safe_error(e))


def send_alert(silence):
    send("EnergyCam has stopped reporting",
         "Nothing has been recorded for %s.\n\n"
         "While it is down no room's state is being written, so these hours"
         " will simply be missing from the record rather than showing as"
         " empty. If this is overnight or a weekend, those are the hours the"
         " system exists to measure.\n\n"
         "Check the machine at 140-H: is it on, is it awake, is the cable in,"
         " and is run_forever.bat still running in its window?"
         % spell(silence))


def send_recovery(gap):
    send("EnergyCam is reporting again",
         "It is back. The gap was %s, and nothing was recorded during it.\n\n"
         "The dashboard draws nothing for those hours rather than drawing"
         " them as empty rooms, so no figure is wrong because of this -- it"
         " is just shorter." % spell(gap))


def main():
    print("Watchdog chal raha hai... (Ctrl+C se rokein)")
    print(">> checking every %d min, alarm after %d min of silence"
          % (CHECK_INTERVAL_SECONDS // 60, MAX_SILENCE_MINUTES))
    print(">> run this somewhere OTHER than the machine it watches. A"
          " watchdog on the machine that died reports nothing.")
    already_alerted = False
    went_quiet_at = None

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
                if silence > timedelta(minutes=MAX_SILENCE_MINUTES):
                    if not already_alerted:
                        went_quiet_at = last_beat
                        send_alert(silence)
                        already_alerted = True
                elif already_alerted:
                    # Saying it is back matters as much as saying it stopped.
                    # Without this nobody knows whether the gap was ten
                    # minutes or the whole night, and a night is the part
                    # worth measuring.
                    gap = now - went_quiet_at if went_quiet_at else None
                    send_recovery(gap)
                    already_alerted = False
                    went_quiet_at = None
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
