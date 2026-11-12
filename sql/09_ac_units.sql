-- EnergyCam: how many of a room's air conditioners are running.
-- Run ONCE as the Supabase project owner (SQL Editor). Safe to run again.
--
-- room_events.ac_state says whether a room is being cooled at all. Since
-- 12 Nov the cameras can read several units in one room -- five of the six
-- 2-ton towers in 141-C Cafe -- and "on" no longer says how much: two
-- towers and six are both "on", and one is three times the load of the
-- other. This column keeps the count the camera saw, so the dashboard can
-- show "5 of 6 running" and the kilowatts behind it.
--
-- NULL means the units were not read (no calibration, the camera did not
-- answer, the reading was refused). The loop writes rows with or without
-- this column, so nothing breaks before this is run; it starts filling the
-- column once room_loop.py is restarted after it.

ALTER TABLE public.room_events
    ADD COLUMN IF NOT EXISTS ac_units_on SMALLINT;

-- No grants to change. energycam_app holds INSERT on the whole table and
-- energycam_dashboard SELECT on the whole table (sql/04_rooms.sql); table
-- grants reach a new column without being repeated. The camera machine still
-- reads back nothing but `timestamp`.
--
-- To check:
--   SELECT column_name, data_type FROM information_schema.columns
--    WHERE table_name = 'room_events' AND column_name = 'ac_units_on';
