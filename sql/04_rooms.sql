-- EnergyCam, multi-room. Run ONCE as the Supabase project owner (SQL Editor),
-- after sql/01_schema.sql and sql/02_roles.sql, before starting room_loop.py.
--
-- The camera machine holds no permission to create or change tables, so this
-- is applied by an administrator rather than by the running system. That was
-- the point of sql/01_schema.sql and it has not changed because there are more
-- rooms now.
--
-- Why a second table rather than more columns on `logs`: `logs` has ac1_status
-- and ac2_status, which is the shape of a system watching one room with two
-- units in it. Thirty rooms with between zero and two units each do not fit
-- that shape, and widening it would break the single-room system and the
-- dashboard that reads it while this one is still being proven.

-- ----------------------------------------------------------- 1. the table
-- A row per CHANGE, not per reading. Thirty rooms sampled every two minutes is
-- about twenty thousand readings a day, nearly all of them identical to the one
-- before -- an empty room at 3am says the same thing seven hundred times a
-- night. Recording only the changes keeps months of history in megabytes, and
-- is also the more useful shape: when a room filled and when it emptied is the
-- question, and the transitions are the answer. The heartbeat table is what
-- separates "nothing changed" from "nothing was watching".

CREATE TABLE IF NOT EXISTS public.room_events (
    id           BIGSERIAL PRIMARY KEY,
    timestamp    TIMESTAMPTZ NOT NULL,
    recorder     TEXT        NOT NULL,
    room         TEXT        NOT NULL,
    status       TEXT        NOT NULL,   -- occupied / empty / unknown
    people       INTEGER,
    empty_since  TIMESTAMPTZ,            -- when this spell of emptiness began
    ac_state     TEXT                    -- on / off / NULL until calibration
);

-- Retention sweeps by time; the dashboard asks for one room's recent history.
CREATE INDEX IF NOT EXISTS room_events_timestamp_idx
    ON public.room_events (timestamp);
CREATE INDEX IF NOT EXISTS room_events_room_time_idx
    ON public.room_events (room, timestamp DESC);

-- ----------------------------------------------------------- 2. privileges
-- Same split as sql/02_roles.sql. The camera machine inserts, and deletes only
-- to enforce retention. It may read the timestamp column and nothing else: that
-- is enough to confirm its own writes are landing, and it is not enough to read
-- back who was in which room. A machine sitting in a corridor cupboard should
-- not be able to answer that question.

GRANT INSERT              ON public.room_events TO energycam_app;
GRANT DELETE              ON public.room_events TO energycam_app;
GRANT SELECT (timestamp)  ON public.room_events TO energycam_app;
GRANT USAGE, SELECT ON SEQUENCE public.room_events_id_seq TO energycam_app;

GRANT SELECT ON public.room_events TO energycam_dashboard;

-- ----------------------------------------------- 3. close the public REST API
-- Supabase publishes everything in `public` through PostgREST to `anon` and
-- `authenticated`. Occupancy data says who was in a building and when, which
-- is not something an anon key found in a browser should be able to read.

ALTER TABLE public.room_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.room_events FROM anon, authenticated;

CREATE POLICY app_insert_rooms ON public.room_events
    FOR INSERT TO energycam_app       WITH CHECK (true);
CREATE POLICY app_delete_rooms ON public.room_events
    FOR DELETE TO energycam_app       USING (true);
CREATE POLICY app_read_rooms   ON public.room_events
    FOR SELECT TO energycam_app       USING (true);
CREATE POLICY dash_read_rooms  ON public.room_events
    FOR SELECT TO energycam_dashboard USING (true);

-- ------------------------------------------------------------ 4. what to check
-- Run these after applying, and keep the output with the security review:
--   SELECT grantee, privilege_type, column_name
--     FROM information_schema.column_privileges
--    WHERE table_name = 'room_events' ORDER BY grantee, column_name;
--   SELECT relname, relrowsecurity FROM pg_class WHERE relname = 'room_events';
--
-- energycam_app should show INSERT and DELETE on the table, SELECT on
-- `timestamp` only, and nothing for anon or authenticated.
