# The machine that stays on

This is the largest hole in the system and no amount of code closes it.

The loop records a room when its state changes. It cannot record anything
while it is not running, and it is not running whenever the laptop goes home.
So the database holds the hours somebody was sitting at the laptop — which
are, almost exactly, the hours when the rooms are occupied and the cooling is
not being wasted.

Everything the dashboard says about nights and weekends is therefore
unmeasured, and the page says so: the coverage warning above the patterns is
not decoration. Until something at 140-H stays on, the figure this project
exists to produce does not exist.

## What it needs to be

Not much.

- **Always on.** No sleep, no hibernate, no "fast startup". A desk PC is
  better than a laptop for exactly this reason: a laptop's default is to
  suspend when the lid closes, and a suspended machine records nothing while
  looking perfectly healthy.
- **On the CCTV network.** The same reach the laptop has now, which today
  means a cable to that VLAN. If it has two network ports, one can stay on
  the office network for the database.
- **Modest.** A pass over ninety-six cameras is mostly waiting; the counting
  is a small model on the processor. Any machine from the last five years
  with 8 GB will do it. No graphics card is needed.
- **Reachable.** Somebody has to be able to log in and look when it misbehaves.

An old office PC is the right answer. It does not need to be a server.

## Setting it up

1. Install Miniconda, create the `hfm_energy` environment and clone the
   repository, exactly as on the laptop. `requirements-local.txt` lists what
   it needs.
2. Copy `.env` across. It holds the recorder credentials and the database
   URL, and it is deliberately not in git.
3. Run one cycle by hand first, so that a configuration problem is found by a
   person rather than by a scheduled task at three in the morning:

   ```
   run_rooms.bat --once
   ```

4. Turn off sleep and hibernation:

   ```
   powercfg /change standby-timeout-ac 0
   powercfg /change hibernate-timeout-ac 0
   powercfg /change monitor-timeout-ac 15
   ```

   On a laptop, also set "closing the lid" to "do nothing" in Power Options.

5. Start it with `run_forever.bat` rather than `run_rooms.bat`. The ordinary
   script is for somebody sitting in front of it: when it stops, they see
   why. On a machine nobody is watching, a loop that stopped at nine in the
   evening means the whole night went unrecorded and nothing said so.
   `run_forever.bat` restarts it, backing off to five minutes so that a
   recorder which has stopped answering is not asked every ten seconds, and
   gives up only on a configuration error, which restarting cannot fix.

6. Make it start at boot. Task Scheduler, a new task:

   - **Run whether user is logged on or not**, and **Run with highest
     privileges**.
   - Trigger: **At startup**, with **Delay task for: 2 minutes** so the
     network is up first.
   - Action: start a program —
     Program: `cmd.exe`
     Arguments: `/c "C:\hfm_energy_project\run_forever.bat --evidence"`
     Start in: `C:\hfm_energy_project`
   - Settings: tick **If the task fails, restart every 5 minutes**, up to 3
     times. Untick **Stop the task if it runs longer than**, which otherwise
     kills it after three days.

7. Check it survives a reboot. Restart the machine, wait five minutes, and
   look at the dashboard: the badge in the header should say **live**, with a
   beat less than three minutes old. If it does not, the task did not start,
   and finding that out now is the entire point of this step.

## How you will know it is working

The dashboard's live badge counts from the heartbeat, which the loop writes
once a minute. Three missed beats and the badge turns red and says how long
it has been silent.

That badge is only useful to somebody looking at the page. `heartbeat_watchdog.py`
is the version that does not need anybody looking: it emails when the beats
stop. Run it somewhere **other** than this machine — a watchdog that lives on
the machine it watches reports nothing when that machine is the thing that
died.

## What this unlocks

Nothing about the system changes. What changes is that the question it was
built to answer becomes answerable:

- Which rooms are cooled through the night, and for how many hours.
- Whether a Monday morning looks different from a Friday evening.
- Whether the figure went down after somebody was told about it — which needs
  two comparable fortnights, and the first of them cannot start until this
  machine is running.
