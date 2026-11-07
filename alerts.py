"""Tell somebody a room is empty and still being cooled.

The dashboard only works while somebody is looking at it, and the hours
worth money are the ones when nobody is: eight at night, Sunday afternoon.
This is the part that speaks without being asked.

Which makes restraint the whole design. An alert that arrives too often is
not a weaker version of a useful alert, it is a filter rule in somebody's
inbox, and after that the system is off without anyone deciding to turn it
off. So:

  One room, one episode, one mention. A room is mentioned when its empty
  period first passes its threshold, and not again for that period. Walking
  in and out of it starts a new period, which is why there is also a
  cooldown: a chair that reads as a person once an hour would otherwise
  manufacture a fresh episode every hour, all night.

  One email, not one per room. Rooms empty together at the end of the day,
  so they are gathered and sent as a list.

  Nothing is claimed that was not measured. Until a room's unit is
  calibrated, its state is unknown, and the mail says the room is empty and
  asks whether the unit is on -- it does not announce waste it cannot see.
  A room whose unit is known to be OFF is never mentioned at all: that is
  the room that got it right.

Off unless asked for. --alerts turns it on; without it the loop prints what
it would have sent and sends nothing.
"""
import os
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formatdate

from schedule import WORKING, describe, period

# Rooms that become due within this of each other travel in one email.
GATHER_SECONDS = 600
# However the empty periods fall, one room is not mentioned twice inside
# this. A camera that invents a person once an hour would otherwise start a
# fresh episode each time and mention the room all night.
ROOM_COOLDOWN = timedelta(hours=2)
# A floor under the whole thing, whatever happens upstream.
MIN_GAP_SECONDS = 900


def recipients():
    """Who to write to. RECEIVER_EMAIL may hold several, comma separated."""
    raw = os.getenv("ALERT_TO") or os.getenv("RECEIVER_EMAIL") or ""
    return [a.strip() for a in raw.split(",") if a.strip()]


def configured():
    return bool(os.getenv("SENDER_EMAIL") and os.getenv("APP_PASSWORD")
                and recipients())


def why_not_configured():
    missing = [name for name in ("SENDER_EMAIL", "APP_PASSWORD")
               if not os.getenv(name)]
    if not recipients():
        missing.append("ALERT_TO (or RECEIVER_EMAIL)")
    return ", ".join(missing)


def spell_wait(minutes):
    if minutes is None:
        return "a while"
    minutes = int(minutes)
    if minutes < 60:
        return "%d min" % minutes
    hours, rest = divmod(minutes, 60)
    return "%dh" % hours if not rest else "%dh %dm" % (hours, rest)


def line_for(room, now):
    """One room, in one line, saying only what is known about it."""
    waited = spell_wait(room.empty_minutes(now))
    if room.ac_state == "on":
        return ("%s — empty %s, and its unit is ON. Switch it off."
                % (room.name, waited))
    if room.ac == "visible":
        return ("%s — empty %s. Its unit has not been calibrated, so nobody"
                " can say whether it is running: please look." % (room.name,
                                                                  waited))
    return ("%s — empty %s. Its unit is not in any camera, so somebody has to"
            " walk past and check it." % (room.name, waited))


class Alerter:
    """Decides what is worth saying, and refuses to say it twice."""

    def __init__(self, send=True, gather_seconds=GATHER_SECONDS,
                 min_gap_seconds=MIN_GAP_SECONDS, cooldown=ROOM_COOLDOWN):
        self.send = send
        self.gather_seconds = gather_seconds
        self.min_gap_seconds = min_gap_seconds
        self.cooldown = cooldown
        self.episode = {}        # room -> the empty_since already mentioned
        self.last_said = {}      # room -> when it was last mentioned
        self.waiting = []        # rooms gathered but not yet sent
        self.first_waited = None
        self.last_sent = None

    def worth_saying(self, room, now, hours=None):
        if not room.due_for_check(now, hours):
            return False
        if self.episode.get(room.name) == room.empty_since:
            return False                      # already said, same episode
        last = self.last_said.get(room.name)
        if last is not None and now - last < self.cooldown:
            return False                      # said recently, whatever the episode
        return True

    def consider(self, rooms, now, hours=None):
        """Gather what is due. Returns the rooms to write about, or []."""
        for room in rooms:
            if self.worth_saying(room, now, hours) and \
                    room.name not in [r.name for r in self.waiting]:
                self.waiting.append(room)
                if self.first_waited is None:
                    self.first_waited = now
        if not self.waiting:
            return []
        if self.last_sent is not None and \
                (now - self.last_sent).total_seconds() < self.min_gap_seconds:
            return []
        # Hold briefly so rooms emptying together arrive together, but never
        # hold the first one so long that the message is stale.
        if (now - self.first_waited).total_seconds() < self.gather_seconds \
                and len(self.waiting) < 6:
            return []
        ready, self.waiting = self.waiting, []
        self.first_waited = None
        for room in ready:
            self.episode[room.name] = room.empty_since
            self.last_said[room.name] = now
        self.last_sent = now
        return ready


def compose(rooms, now, hours=None):
    after = period(now, hours) != WORKING
    subject = "%s%d room%s empty%s" % (
        "[after hours] " if after else "",
        len(rooms), "" if len(rooms) == 1 else "s",
        " and cooled" if any(r.ac_state == "on" for r in rooms) else "")
    lines = ["%s, %s." % (now.strftime("%A %d %B, %H:%M"), describe(now, hours)),
             ""]
    lines += ["  - " + line_for(r, now) for r in rooms]
    lines += ["",
              "Nothing here is a reading of an electricity meter. It is a"
              " count of people from the cameras already on the building, and"
              " where a unit has not been calibrated its state is unknown"
              " rather than assumed.",
              "",
              "Sent by EnergyCam. To stop these, run the loop without"
              " --alerts."]
    return subject, "\n".join(lines)


def deliver(subject, body, to=None, host="smtp.gmail.com", port=465):
    """Send it. Raises on failure -- the caller decides what that means."""
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("APP_PASSWORD")
    to = to or recipients()
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message.set_content(body)
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(),
                          timeout=30) as server:
        server.login(sender, password)
        server.send_message(message)
    return len(to)
