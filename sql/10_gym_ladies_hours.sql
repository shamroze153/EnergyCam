-- 141 gym, ladies' hours: remove what was written before private_hours.
--
-- The 141 gym is ladies-only 15:00-20:00. Since 12 Nov 16:45 the loop does
-- not open its camera in those hours (rooms.yaml private_hours), but counts
-- had already been written in them: 18 rows on 11 Nov (17:44-19:51) and 9
-- on 12 Nov (15:10-16:39). Shamroze asked for them all to go ("Haan, delete
-- karo", "Haan, woh bhi", 12 Nov). The camera machine's role cannot delete
-- a room's rows -- by design, and it stays that way -- so an administrator
-- runs this once in the Supabase SQL editor.
--
-- Each day that had rows in those hours gets one "unknown" row at 15:00 in
-- their place, so the hours read as not watched rather than as the last
-- state before three carrying on. The loop's own "unknown" row of 12 Nov
-- 16:49:45 stays. Counts only: no picture was ever in the database.
--
-- Checked read-only before writing this (the same conditions): 27 rows,
-- and 15:00 "unknown" rows for 11 and 12 Nov.

BEGIN;

CREATE TEMP TABLE gym_days ON COMMIT DROP AS
SELECT DISTINCT (timestamp AT TIME ZONE 'Asia/Karachi')::date AS day
  FROM public.room_events
 WHERE room = '141 Gym'
   AND timestamp < '2026-11-12 16:49:45+05'
   AND (timestamp AT TIME ZONE 'Asia/Karachi')::time >= '15:00'
   AND (timestamp AT TIME ZONE 'Asia/Karachi')::time <  '20:00';

DELETE FROM public.room_events
 WHERE room = '141 Gym'
   AND timestamp < '2026-11-12 16:49:45+05'
   AND (timestamp AT TIME ZONE 'Asia/Karachi')::time >= '15:00'
   AND (timestamp AT TIME ZONE 'Asia/Karachi')::time <  '20:00';

INSERT INTO public.room_events
       (timestamp, recorder, room, status, people, empty_since, ac_state)
SELECT (day + time '15:00') AT TIME ZONE 'Asia/Karachi',
       'cd_nvr2', '141 Gym', 'unknown', NULL, NULL, NULL
  FROM gym_days;

COMMIT;

-- Afterwards this should say 0:
--   SELECT count(*) FROM public.room_events
--    WHERE room = '141 Gym' AND status <> 'unknown'
--      AND (timestamp AT TIME ZONE 'Asia/Karachi')::time >= '15:00'
--      AND (timestamp AT TIME ZONE 'Asia/Karachi')::time <  '20:00';
