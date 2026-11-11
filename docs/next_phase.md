# EnergyCam — the next phase

*11 November 2026. What the system can do now, and what to do with it.*

The cameras now count people in 74 rooms on 167 cameras across both
campuses, around the clock when the loop runs. That part works. What the
system **cannot** yet say is whether an air conditioner was actually on: one
unit of about forty is calibrated, so every "Rs at stake" is an upper bound
that assumes a unit in an empty room was running. Turning that guess into a
measurement — and then into rooms actually switched off — is the next phase.

## 1. Prove it: measured money instead of an upper bound

| | What | Cost | What it gives |
|---|---|---|---|
| 1 | **Calibrate the units a camera can see.** `python field_audit.py` takes a full-size picture of every camera in every AC room; the boxes round each display are drawn from those, then `calibrate_room.py` confirms each with one on/off. | Free | The units in frame read as on or off, for real |
| 2 | **Smart plugs or energy monitors on the top 10 rooms.** Analysis → *Where to start* lists them, ranked by cost. | A few thousand rupees a unit | Real on/off and real kWh for the rooms that matter most |
| 3 | **Read the two meters and the solar every day** (Meters page form). After about four weeks: kWh per empty, cooled room-hour. | Free | Replaces the 1.2 kW guess with a measured figure |

## 2. Act: savings only happen when something is switched off

| | What | Notes |
|---|---|---|
| 4 | **Alerts on.** A message to one person in Admin/Facilities when a room has been empty 45 minutes with a unit. | `alerts.py` is built; it needs the mail (or WhatsApp) details |
| 5 | **The closing round.** At 7:30 in the evening, the rooms still worth a walk, as a list for the guard. | The Overview's *Worth a walk* is this list already |
| 6 | **Timers** on rooms that are reliably empty after a set hour. | Numbers & history already finds them |
| 7 | **Switch-off by itself** (IR blaster) in the rooms that are left on again and again. | After 4–6 have been tried |

## 3. Cut the bill another way

| | What | Size |
|---|---|---|
| 8 | **The demand charge.** October charged a maximum demand of 38 kW against a sanctioned 19 — Rs 47,500 where 19 kW costs Rs 23,750. Starting the units floor by floor rather than all at ten, or a load revision. | About Rs 285,000 a year |
| 9 | **The peak tariff, 6:30–10:30 evening.** Empty rooms in those hours cost 21% more a unit; they are the first to alert on. | Analysis shows the peak hours per room |
| 10 | **Query the impossible bills.** First floor, July 2026: 41,145 units, more than a 37 kW connection can draw in a month. | About Rs 2.4 million billed |
| 11 | **Use the solar.** Move what can move (RO plant, pumps) into 11 to 3. | Meters page shows what the panels make |

## 4. Use the occupancy beyond the air conditioning

* **Meeting rooms** — which are rarely used, and could be closed or cooled
  only when booked.
* **Departments** — first in and last out per department sets when each
  area needs cooling at all.
* **A weekly page for management** — at stake, the top rooms, against last
  week.

## 5. Keep it solid

* An **always-on mini PC with a UPS** at 140-H instead of the laptop:
  nights without data cannot show a saving.
* **141-C/D's remaining recorders** (XVR 1–4, the DVR) — only where they
  cover rooms with units.
* **`field_audit.py` once a month** — every room's count against its
  cameras, and a picture of every disagreement, to catch the chair or
  poster read as a person.

## Suggested order

1. This week: run `python field_audit.py`, send the zip; calibrate from it.
2. Buy plugs/monitors for the top 10 rooms; switch alerts on to one person.
3. Two weeks with alerts off, two with them on; the meters say the difference.
4. The demand charge and the July bill, in parallel — they need a phone call,
   not a camera.
