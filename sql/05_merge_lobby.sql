-- One place that was recorded as two rooms.
--
-- nvr1 channel 22 and xvr3 channel 16 look at the same first floor lobby at
-- 140-H: the same wooden floor, the same glass balustrade, the same man in
-- the same brown armchair, in frames a minute apart on 7 November 2026. They
-- were two rooms only because a room used to belong to a single recorder.
--
-- rooms.yaml now has them as one room called "H First Floor Lobby". The rows
-- already written under the old name belong to that same place, and without
-- this they are stranded: the dashboard joins its figures to rooms.yaml, so
-- rows under a name that no longer exists are silently dropped, and the
-- lobby's history restarts from nothing.
--
-- Run it once, in the Supabase SQL editor, as the owner. It is safe to run
-- twice: the second time it matches nothing.

BEGIN;

-- What is about to move. Read this before the UPDATE if you want to see it.
SELECT 'before' AS stage, room, count(*) AS rows,
       min(timestamp) AS earliest, max(timestamp) AS latest
FROM room_events
WHERE room IN ('H First Floor Lobby', 'H First Floor Lobby (NVR 1)')
GROUP BY room
ORDER BY room;

UPDATE room_events
   SET room = 'H First Floor Lobby'
 WHERE room = 'H First Floor Lobby (NVR 1)';

-- The recorder column stays as it was written. It records which recorder the
-- loop was filed under when that row was made, and rewriting history to say
-- otherwise would be a lie about the past: those readings really did come
-- from nvr1, before the two were joined.

SELECT 'after' AS stage, room, count(*) AS rows,
       min(timestamp) AS earliest, max(timestamp) AS latest
FROM room_events
WHERE room = 'H First Floor Lobby'
GROUP BY room;

COMMIT;
