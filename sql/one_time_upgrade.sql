-- HFM one-time database upgrade  (run ONCE in Supabase -> SQL Editor)
--
-- WHEN: after downloading the new code, BEFORE starting the new unified_system.py.
--   1. Stop the old unified_system.py / run_system.bat (close the window).
--   2. Paste this whole file in Supabase SQL Editor -> Run.
--   3. Start the new version.
-- Do NOT run it a second time (it would shift the times again).

BEGIN;

-- 1) Old code saved Pakistan wall-clock time without a time zone, so Supabase
--    stored every old row 5 hours in the future. Move them back.
UPDATE logs      SET timestamp = timestamp - interval '5 hours';
UPDATE heartbeat SET timestamp = timestamp - interval '5 hours';

-- 2) Phone detection was removed; drop the unused column.
ALTER TABLE logs DROP COLUMN IF EXISTS phone_count;

COMMIT;

-- Check: the newest row should now be a few minutes ago in Pakistan time.
SELECT max(timestamp) AT TIME ZONE 'Asia/Karachi' AS newest_row_pkt,
       now()          AT TIME ZONE 'Asia/Karachi' AS now_pkt
FROM logs;
