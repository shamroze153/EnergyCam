-- EnergyCam schema. Run ONCE as the Supabase project owner (SQL Editor), before
-- starting the camera system.
--
-- Why this file exists: unified_system.py used to run CREATE TABLE itself on every
-- start, which meant the credential on the camera PC needed permission to change the
-- schema. A machine that only writes log rows must not be able to create, alter or
-- drop tables, so schema changes live here and are applied by an administrator.

CREATE TABLE IF NOT EXISTS public.logs (
    id            SERIAL PRIMARY KEY,
    timestamp     TIMESTAMPTZ NOT NULL,
    room_name     TEXT,
    room_status   TEXT,
    ac1_status    TEXT,
    ac2_status    TEXT,
    person_count  INTEGER,
    alert_sent    INTEGER
);

CREATE TABLE IF NOT EXISTS public.heartbeat (
    id         SERIAL PRIMARY KEY,
    timestamp  TIMESTAMPTZ NOT NULL
);

-- Retention deletes and the dashboard both filter on timestamp.
CREATE INDEX IF NOT EXISTS logs_timestamp_idx      ON public.logs (timestamp);
CREATE INDEX IF NOT EXISTS heartbeat_timestamp_idx ON public.heartbeat (timestamp);
