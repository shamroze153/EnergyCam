-- 141 gym, ladies' hours: remove what was written before private_hours.
--
-- The 141 gym is ladies-only 15:00-20:00. Since 12 Nov 16:45 the loop does
-- not open its camera in those hours (rooms.yaml private_hours), but on
-- 12 Nov nine counts had already been written between 15:10 and 16:39.
-- Shamroze asked for them to go ("Haan, delete karo", 12 Nov). The camera
-- machine's role cannot delete a room's rows -- by design, and it stays
-- that way -- so an administrator runs this once in the Supabase SQL
-- editor.
--
-- It deletes those rows and writes one "unknown" row at 15:00 in their
-- place, so the hours read as not watched rather than as the last state
-- before three carrying on. The loop's own "unknown" row at 16:49:45 stays.
-- Counts only: no picture was ever in the database.

BEGIN;

DELETE FROM public.room_events
 WHERE room = '141 Gym'
   AND timestamp >= '2026-11-12 15:00:00+05'
   AND timestamp <  '2026-11-12 16:49:45+05';

INSERT INTO public.room_events
       (timestamp, recorder, room, status, people, empty_since, ac_state)
VALUES ('2026-11-12 15:00:00+05', 'cd_nvr2', '141 Gym', 'unknown',
        NULL, NULL, NULL);

COMMIT;

-- Earlier days (10-11 Nov) also have gym counts between 15:00 and 20:00,
-- from before anyone knew. Only if Shamroze says so, remove the leading
-- "-- " from the four lines below and run them as well:
--
-- DELETE FROM public.room_events
--  WHERE room = '141 Gym'
--    AND timestamp < '2026-11-12 15:00:00+05'
--    AND (timestamp AT TIME ZONE 'Asia/Karachi')::time >= '15:00'
--    AND (timestamp AT TIME ZONE 'Asia/Karachi')::time <  '20:00';
