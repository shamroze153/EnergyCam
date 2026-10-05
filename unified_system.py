from ultralytics import YOLO
import cv2
import threading
from ac_config import check_ac_status, detect_light_mode
from privacy_blur import anonymize
import numpy as np
import smtplib
import imaplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import make_msgid, formatdate
import time
import os
import psycopg2
from datetime import datetime, time as dtime, timedelta, timezone
from collections import deque
from dotenv import load_dotenv

load_dotenv()

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
rtsp_url = os.getenv("RTSP_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

model = YOLO("yolov8n.pt")

ROOM_NAME = "Demo Room"

UNIT_RATE = 55

EMPTY_THRESHOLD_SECONDS = 10
CLOSURE_CONFIRM_SECONDS = 20
LOG_INTERVAL_SECONDS = 30
HEARTBEAT_INTERVAL_SECONDS = 1800

# Data retention: logs/heartbeat rows older than this are deleted once a day
RETENTION_DAYS = 90
RETENTION_CHECK_INTERVAL_SECONDS = 24 * 3600

# After-hours: alerts in this window get "[AFTER-HOURS]" in the email subject
AFTER_HOURS_START = dtime(19, 0)   # 7:00 PM
AFTER_HOURS_END = dtime(8, 0)      # 8:00 AM

# Email copies: delete each sent alert from the sender's Gmail Sent + Trash
DELETE_SENT_COPIES = True

# Pakistan time for all DB timestamps (needs the "tzdata" package on Windows)
try:
    from zoneinfo import ZoneInfo
    PK_TZ = ZoneInfo("Asia/Karachi")
except Exception:
    PK_TZ = timezone(timedelta(hours=5), "PKT")   # Pakistan has no DST

AC_HISTORY_LEN = 6
AC_STABILITY_RATIO = 0.7

RECONNECT_GRACE_FRAMES = 3
BLANK_FRAME_STD_THRESHOLD = 5
# Night/dark frames have low contrast but are still valid. A frame darker than
# DARK_FRAME_MEAN_MAX only needs std above DARK_FRAME_STD_THRESHOLD; a truly
# blank/corrupt frame (flat grey/green) has std close to 0.
DARK_FRAME_MEAN_MAX = 60
DARK_FRAME_STD_THRESHOLD = 1.5
MAX_CONSECUTIVE_BAD_FRAMES = 15
NO_FRAME_TIMEOUT_SECONDS = 8
COUNT_CONFIDENCE = 0.5
# A person must be at least this confident for the room to count as OCCUPIED.
# Lower (e.g. 0.35) if real people are missed at night; raise if chairs/
# reflections still make an empty room OCCUPIED.
PRESENCE_CONFIDENCE = 0.5

ac1_history = deque(maxlen=AC_HISTORY_LEN)
ac2_history = deque(maxlen=AC_HISTORY_LEN)
person_history = deque(maxlen=4)
frame_buffer = deque(maxlen=3)
light_mode_history = deque(maxlen=10)   # smooths DAY/NIGHT switching


class LiveCameraReader:
    def __init__(self, url):
        self.url = url
        self.cap = cv2.VideoCapture(url)
        self.lock = threading.Lock()
        self.latest_frame = None
        self.ret = False
        self.frame_seq = 0
        self.last_frame_time = time.time()
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        while self.running:
            try:
                ret, frame = self.cap.read()
            except Exception:
                ret, frame = False, None
            with self.lock:
                self.ret = ret
                if ret:
                    self.latest_frame = frame
                    self.frame_seq += 1
                    self.last_frame_time = time.time()

    def read(self):
        with self.lock:
            return self.ret, self.latest_frame, self.frame_seq

    def seconds_since_last_frame(self):
        with self.lock:
            return time.time() - self.last_frame_time

    def isOpened(self):
        return self.cap.isOpened()

    def release(self):
        self.running = False
        self.thread.join(timeout=2)
        try:
            self.cap.release()
        except Exception:
            pass


def now_pkt():
    return datetime.now(PK_TZ)


def is_after_hours(now=None):
    t = (now or now_pkt()).time()
    if AFTER_HOURS_START <= AFTER_HOURS_END:
        return AFTER_HOURS_START <= t < AFTER_HOURS_END
    return t >= AFTER_HOURS_START or t < AFTER_HOURS_END   # window crosses midnight


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def setup_database():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ,
            room_name TEXT,
            room_status TEXT,
            ac1_status TEXT,
            ac2_status TEXT,
            person_count INTEGER,
            alert_sent INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS heartbeat (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()


def log_to_db(room_name, room_status, ac1_status, ac2_status, person_count, alert_sent):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO logs (timestamp, room_name, room_status, ac1_status, ac2_status, person_count, alert_sent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (now_pkt(), room_name, room_status, ac1_status, ac2_status, person_count, alert_sent))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f">> DB log failed: {e}")


def log_heartbeat():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO heartbeat (timestamp) VALUES (%s)", (now_pkt(),))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f">> Heartbeat log failed: {e}")


def cleanup_old_rows():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs WHERE timestamp < NOW() - make_interval(days => %s)", (RETENTION_DAYS,))
        logs_deleted = cursor.rowcount
        cursor.execute("DELETE FROM heartbeat WHERE timestamp < NOW() - make_interval(days => %s)", (RETENTION_DAYS,))
        hb_deleted = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        print(f">> Retention: {RETENTION_DAYS} din se purani rows delete — logs={logs_deleted}, heartbeat={hb_deleted}")
    except Exception as e:
        print(f">> Retention cleanup failed: {e}")


def smoothed_status(history, raw_reading, maxlen, threshold_ratio=0.5):
    history.append(raw_reading)
    on_count = sum(history)
    return on_count >= max(1, int(len(history) * threshold_ratio))


def is_frame_usable(frame):
    if frame is None:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    std = np.std(gray)
    if std > BLANK_FRAME_STD_THRESHOLD:
        return True
    # dark night frame: low contrast is normal, only reject if completely flat
    return gray.mean() < DARK_FRAME_MEAN_MAX and std > DARK_FRAME_STD_THRESHOLD


def pick_clean_frame(buffer, fallback):
    for f in reversed(buffer):
        if is_frame_usable(f):
            return f
    return fallback


def smoothed_light_mode(frame):
    light_mode_history.append(detect_light_mode(frame))
    return "NIGHT" if light_mode_history.count("NIGHT") > len(light_mode_history) / 2 else "DAY"


def _imap_find_folders(imap):
    """Gmail's Sent and Trash folder names (they differ by account language)."""
    sent, trash = '"[Gmail]/Sent Mail"', '"[Gmail]/Trash"'
    typ, folders = imap.list()
    if typ == "OK":
        for raw in folders:
            line = raw.decode(errors="ignore") if isinstance(raw, bytes) else str(raw)
            name = line.split(' "/" ')[-1].strip()
            if "\\Sent" in line:
                sent = name
            elif "\\Trash" in line:
                trash = name
    return sent, trash


def _imap_search(imap, message_id):
    try:
        typ, data = imap.uid("SEARCH", "X-GM-RAW", f'"rfc822msgid:{message_id}"')
    except imaplib.IMAP4.error:
        typ = "NO"
    if typ != "OK":
        typ, data = imap.uid("SEARCH", "HEADER", "Message-ID", message_id)
    return data[0].split() if typ == "OK" and data and data[0] else []


def delete_sent_copy(message_id, attempts=4, wait_seconds=5):
    """Moves the sent email to Trash, then deletes it from Trash for good.
    Runs in a background thread; any failure only prints a warning."""
    try:
        for attempt in range(attempts):
            time.sleep(wait_seconds)   # Gmail takes a few seconds to file it in Sent
            imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=20)
            try:
                imap.login(SENDER_EMAIL, APP_PASSWORD)
                sent_folder, trash_folder = _imap_find_folders(imap)

                imap.select(sent_folder)
                uids = _imap_search(imap, message_id)
                if not uids:
                    continue
                for uid in uids:
                    imap.uid("COPY", uid, trash_folder)   # Gmail: copy to Trash = move to Trash
                    imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                imap.expunge()

                imap.select(trash_folder)
                for uid in _imap_search(imap, message_id):
                    imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
                imap.expunge()
                print(">> Sent-folder copy delete ho gayi (Sent + Trash).")
                return True
            finally:
                try:
                    imap.logout()
                except Exception:
                    pass
        print(">> WARNING: Sent-folder copy nahi mili — delete nahi hui.")
    except Exception as e:
        print(f">> WARNING: Sent-folder copy delete nahi ho saki: {e}")
    return False


def send_email(subject, message_text, image_frame=None):
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg["Date"] = formatdate(localtime=True)
    message_id = make_msgid(domain="hfm.alert")
    msg["Message-ID"] = message_id
    msg.attach(MIMEText(message_text))

    if image_frame is not None:
        # PRIVACY: blur people + screens BEFORE anything leaves this machine.
        # If blurring fails for any reason, send the email WITHOUT the image
        # (never send an unblurred snapshot). Snapshot lives only in memory,
        # it is never written to disk.
        try:
            safe_frame = anonymize(image_frame, model)
        except Exception as e:
            print(f">> Blur failed, snapshot NOT attached: {e}")
            safe_frame = None

        if safe_frame is not None:
            success, encoded_img = cv2.imencode(".jpg", safe_frame)
            if success:
                img_attachment = MIMEImage(encoded_img.tobytes(), name="snapshot.jpg")
                msg.attach(img_attachment)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f">> EMAIL SENT: {subject}")
        if DELETE_SENT_COPIES:
            threading.Thread(target=delete_sent_copy, args=(message_id,), daemon=True).start()
        return True
    except Exception as e:
        print(f">> EMAIL FAILED: {e}")
        return False


def connect_camera():
    return LiveCameraReader(rtsp_url)


def main():
    setup_database()

    cap = connect_camera()

    start_time = time.time()
    empty_since = None
    alert_sent_this_cycle = False
    alert_active = False
    alert_fired_time = None
    closure_pending_since = None
    last_log_time = -999
    last_heartbeat_time = -HEARTBEAT_INTERVAL_SECONDS   # heartbeat right at startup
    last_retention_time = -RETENTION_CHECK_INTERVAL_SECONDS   # retention check at startup
    frames_since_reconnect = RECONNECT_GRACE_FRAMES
    consecutive_bad_frames = 0
    last_processed_seq = -1
    alert_pending_log = False   # alert sent since the last DB log row

    print("System chal raha hai... (Ctrl+C se rokein)")

    while True:
        ret, frame, seq = cap.read()

        if not ret or frame is None or cap.seconds_since_last_frame() > NO_FRAME_TIMEOUT_SECONDS:
            print("Frame nahi mila — camera reconnect kar raha hai...")
            try:
                cap.release()
            except Exception:
                pass
            time.sleep(2)
            cap = connect_camera()
            frames_since_reconnect = 0
            consecutive_bad_frames = 0
            last_processed_seq = -1
            time.sleep(1)
            continue

        if seq == last_processed_seq:
            time.sleep(0.05)
            continue
        last_processed_seq = seq

        if not is_frame_usable(frame):
            consecutive_bad_frames += 1
            print(f">> Corrupt/blank frame — skip kar raha hai... ({consecutive_bad_frames}/{MAX_CONSECUTIVE_BAD_FRAMES})")
            if consecutive_bad_frames >= MAX_CONSECUTIVE_BAD_FRAMES:
                print(">> Bohat der se corrupt frames aa rahe hain — camera ko force-reconnect kar raha hai...")
                try:
                    cap.release()
                except Exception:
                    pass
                time.sleep(2)
                cap = connect_camera()
                frames_since_reconnect = 0
                consecutive_bad_frames = 0
                last_processed_seq = -1
            continue

        consecutive_bad_frames = 0

        if frames_since_reconnect < RECONNECT_GRACE_FRAMES:
            frames_since_reconnect += 1
            continue

        frame_buffer.append(frame)
        current_time = time.time() - start_time

        light_mode = smoothed_light_mode(frame)

        try:
            # Persons only. Presence uses PRESENCE_CONFIDENCE (see top of file).
            # NOTE: night (IR) accuracy must be verified in testing with lights off.
            results = model(frame, classes=[0], imgsz=640, verbose=False)
            boxes = results[0].boxes
            class_ids = boxes.cls.tolist() if len(boxes) > 0 else []
            confs = boxes.conf.tolist() if len(boxes) > 0 else []
            # Counting: only confident detections (avoids chairs/reflections being counted)
            person_count = sum(1 for c, cf in zip(class_ids, confs) if c == 0.0 and cf >= COUNT_CONFIDENCE)
            # Presence: only confident detections, so low-confidence ghosts (chairs,
            # reflections) don't keep an empty room OCCUPIED and block the alert
            person_present_raw = any(c == 0.0 and cf >= PRESENCE_CONFIDENCE for c, cf in zip(class_ids, confs))
            person_present = smoothed_status(person_history, person_present_raw, 4)
            room_empty = not person_present

            ac1_result = check_ac_status(frame, "left_ac", light_mode)
            ac2_result = check_ac_status(frame, "right_ac", light_mode)
            ac1_raw = ac1_result["status"] == "ON"
            ac2_raw = ac2_result["status"] == "ON"
            ac1_on = smoothed_status(ac1_history, ac1_raw, AC_HISTORY_LEN, AC_STABILITY_RATIO)
            ac2_on = smoothed_status(ac2_history, ac2_raw, AC_HISTORY_LEN, AC_STABILITY_RATIO)
            ac_on = ac1_on or ac2_on
        except Exception as e:
            print(f">> Corrupt frame skip kiya: {e}")
            continue

        closure_condition = alert_active and (not room_empty or not ac_on)
        if closure_condition:
            if closure_pending_since is None:
                closure_pending_since = current_time
            elif current_time - closure_pending_since >= CLOSURE_CONFIRM_SECONDS:
                duration_min = (current_time - alert_fired_time) / 60
                reason = "Someone returned to the room" if not room_empty else "AC was switched off"
                clean_frame = pick_clean_frame(frame_buffer, frame)
                print(">> Resolve condition confirmed — resolved email bhej raha hai...")
                send_email(
                    f"HFM Alert Resolved: {ROOM_NAME}",
                    f"Update: {reason} in {ROOM_NAME}.\nThe earlier energy-waste alert is now resolved.\nDuration of waste: {duration_min:.1f} minutes.",
                    image_frame=clean_frame
                )
                alert_active = False
                alert_sent_this_cycle = False
                closure_pending_since = None
        else:
            closure_pending_since = None

        if room_empty:
            if empty_since is None:
                empty_since = current_time
            empty_duration = current_time - empty_since
        else:
            empty_since = None
            empty_duration = 0
            alert_sent_this_cycle = False

        should_alert = room_empty and ac_on and empty_duration >= EMPTY_THRESHOLD_SECONDS
        if should_alert and not alert_sent_this_cycle:
            clean_frame = pick_clean_frame(frame_buffer, frame)
            print(">> Alert trigger — blur + email bhej raha hai...")
            subject = f"HFM Energy Alert: {ROOM_NAME} Empty but AC ON"
            if is_after_hours():
                subject = "[AFTER-HOURS] " + subject
            sent_ok = send_email(
                subject,
                f"{ROOM_NAME} khaali hai lekin AC ON hai (AC1={ac1_on}, AC2={ac2_on}) — energy waste ho raha hai.\nSnapshot attached.",
                image_frame=clean_frame
            )
            alert_sent_this_cycle = True
            alert_pending_log = alert_pending_log or sent_ok
            if sent_ok:
                alert_active = True
                alert_fired_time = current_time

        if current_time - last_log_time >= LOG_INTERVAL_SECONDS:
            room_status = "EMPTY" if room_empty else "OCCUPIED"
            log_to_db(ROOM_NAME, room_status, "ON" if ac1_on else "OFF", "ON" if ac2_on else "OFF", person_count, int(alert_pending_log))
            last_log_time = current_time
            print(f">> LOGGED: t={current_time:.0f}s | {light_mode} | {room_status} | AC1={'ON' if ac1_on else 'OFF'} AC2={'ON' if ac2_on else 'OFF'} | People={person_count} | EmailSentNow={alert_pending_log}")
            alert_pending_log = False

        if current_time - last_heartbeat_time >= HEARTBEAT_INTERVAL_SECONDS:
            log_heartbeat()
            last_heartbeat_time = current_time
            print(">> Heartbeat logged.")

        if current_time - last_retention_time >= RETENTION_CHECK_INTERVAL_SECONDS:
            cleanup_old_rows()
            last_retention_time = current_time

    cap.release()


if __name__ == "__main__":
    main()