"""When the building is in use, and what that changes.

A room empty for forty-five minutes at two in the afternoon is a room whose
occupant is in a meeting. The same room empty for forty-five minutes at eleven
at night is a room nobody is coming back to. The wait before reporting one
should not be the same number, and until now it was.

So there are two waits. Inside operating hours, the long one, because people
return. Outside them -- evenings, nights, and all of Saturday and Sunday --
a short one, because they do not.

This lives in its own file on purpose. The loop decides when to alert and the
dashboard decides what to colour, and if they worked it out separately they
would drift: the dashboard would show four rooms wanting attention while the
alerts fired on six, and nobody would be able to say which was right.
"""

from datetime import timedelta, timezone

# A fixed five-hour offset rather than a named zone. Both callers have to work:
# the loop hands this a stdlib datetime and the dashboard hands it a pandas
# Timestamp, and only one of those has tz_convert. astimezone is on both.
# Pakistan has not observed daylight saving since 2009, so a fixed offset is
# not an approximation here, and it needs no timezone database installed --
# which on Windows is a package that may or may not be there.
PKT = timezone(timedelta(hours=5))

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

DEFAULT_HOURS = {
    "operations": {"days": ["mon", "tue", "wed", "thu", "fri"],
                   "start": "10:00", "end": "20:00"},
    "off_hours_empty_after_minutes": 10,
}


def _minutes(clock):
    hours, _, mins = str(clock).partition(":")
    return int(hours) * 60 + int(mins or 0)


def in_operations(when, hours=None):
    """Is the building meant to be in use at this moment?

    `when` is any timezone-aware timestamp -- a stdlib datetime from the loop
    or a pandas Timestamp from the dashboard -- and is read in Pakistan time,
    because the question is about the working day in Karachi, not about UTC.
    """
    hours = hours or DEFAULT_HOURS
    window = hours.get("operations", DEFAULT_HOURS["operations"])
    local = when.astimezone(PKT)
    days = [d.strip().lower()[:3] for d in window.get("days", [])]
    if DAY_NAMES[local.weekday()] not in days:
        return False
    minute = local.hour * 60 + local.minute
    start, end = _minutes(window.get("start", "00:00")), \
        _minutes(window.get("end", "23:59"))
    if start <= end:
        return start <= minute < end
    # A window that runs past midnight, for a shift that does.
    return minute >= start or minute < end


WORKING, AFTER_HOURS, WEEKEND = "working hours", "after hours", "weekend"


def period(when, hours=None):
    """Which kind of time this is: working, after hours, or the weekend."""
    hours = hours or DEFAULT_HOURS
    if in_operations(when, hours):
        return WORKING
    local = when.astimezone(PKT)
    days = [d.strip().lower()[:3]
            for d in hours.get("operations",
                               DEFAULT_HOURS["operations"]).get("days", [])]
    return AFTER_HOURS if DAY_NAMES[local.weekday()] in days else WEEKEND


def split_by_period(start, end, hours=None):
    """Minutes between two moments, split by what kind of time they fall in.

    The reason this exists: a room left cooling through a lunch break costs
    about fifty rupees, and the same room left cooling from eight at night
    until ten in the morning costs about nine hundred. One night is worth
    eighteen lunch breaks. Totalling them together hides that, and a total
    that hides where the money is will send people chasing the wrong thing.

    Walked in chunks aligned to the hour, which is as fine as the question
    needs: no operating window here turns over mid-hour.
    """
    buckets = {WORKING: 0.0, AFTER_HOURS: 0.0, WEEKEND: 0.0}
    if end <= start:
        return buckets
    cursor = start
    while cursor < end:
        # the next hour boundary in local time, or the end, whichever is first
        local = cursor.astimezone(PKT)
        step = 60 - local.minute
        nxt = cursor + timedelta(minutes=step)
        if nxt > end:
            nxt = end
        buckets[period(cursor, hours)] += (nxt - cursor).total_seconds() / 60.0
        cursor = nxt
    return buckets


def wait_before_reporting(room_minutes, when, hours=None):
    """How long a room may sit empty before it is worth reporting, right now.

    None means never report this room, whatever the hour -- a corridor has no
    unit and a server room is cooled on purpose.
    """
    if not room_minutes:
        return None
    if in_operations(when, hours):
        return room_minutes
    short = (hours or DEFAULT_HOURS).get(
        "off_hours_empty_after_minutes",
        DEFAULT_HOURS["off_hours_empty_after_minutes"])
    # Never longer than the room's own figure. A room told to report after ten
    # minutes in the day should not wait longer at midnight because of a
    # badly chosen global default.
    return min(room_minutes, short)


def describe(when, hours=None):
    """A short phrase for the dashboard, so the thresholds make sense."""
    hours = hours or DEFAULT_HOURS
    if in_operations(when, hours):
        window = hours.get("operations", DEFAULT_HOURS["operations"])
        return "operating hours (%s–%s)" % (window.get("start"),
                                                 window.get("end"))
    local = when.astimezone(PKT)
    short = hours.get("off_hours_empty_after_minutes",
                      DEFAULT_HOURS["off_hours_empty_after_minutes"])
    if DAY_NAMES[local.weekday()] in ("sat", "sun"):
        return "weekend — reporting after %d min" % short
    return "outside operating hours — reporting after %d min" % short
