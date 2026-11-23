-- EnergyCam: the Progress tab's numbers on the hosted page (23 Nov 2026).
-- Run ONCE as the Supabase project owner (SQL Editor). Safe to run again.
--
-- The Progress tab (the productivity project HR approved) is worked out on
-- the office laptop, from files that never leave it: which employee sits
-- at which desk (progress.yaml), the seat notes, the desk pictures and the
-- day's videos. On the hosted page there is none of that, so the tab said
-- "runs on the office laptop" and showed nothing.
--
-- This table carries the NUMBERS only, one row an employee a day: a code
-- (P1..P5), the department, first in / last out / last seen, the hours at
-- the desk by activity, the week's strips, the project's stages. Never a
-- name (names stay in progress.yaml on the laptop) and never a picture.
-- The laptop's loop (energycam_app) writes it every ten minutes; the hosted
-- dashboard (energycam_dashboard) reads it. Nobody else: row level
-- security is on and the public API roles are shut out, as for every
-- other table (sql/02_roles.sql). The tab itself stays behind its own
-- password, PROGRESS_PASSWORD, in the app's secrets.
--
-- Until this is run the loop says so once and carries on; nothing breaks.

CREATE TABLE IF NOT EXISTS public.progress_days (
    day         DATE        NOT NULL,
    code        TEXT        NOT NULL,
    payload     JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (day, code)
);

ALTER TABLE public.progress_days ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.progress_days FROM PUBLIC, anon, authenticated;

-- The camera machine: writes (an upsert: INSERT ... ON CONFLICT (day, code)
-- DO UPDATE), and may read back only the key that upsert compares. No
-- DELETE, no DDL.
GRANT INSERT, UPDATE        ON public.progress_days TO energycam_app;
GRANT SELECT (day, code)    ON public.progress_days TO energycam_app;
-- The hosted dashboard: reads, never writes.
GRANT SELECT                ON public.progress_days TO energycam_dashboard;

DROP POLICY IF EXISTS app_insert_progress ON public.progress_days;
DROP POLICY IF EXISTS app_update_progress ON public.progress_days;
DROP POLICY IF EXISTS app_read_progress   ON public.progress_days;
DROP POLICY IF EXISTS dash_read_progress  ON public.progress_days;
CREATE POLICY app_insert_progress ON public.progress_days
    FOR INSERT TO energycam_app WITH CHECK (true);
CREATE POLICY app_update_progress ON public.progress_days
    FOR UPDATE TO energycam_app USING (true) WITH CHECK (true);
CREATE POLICY app_read_progress   ON public.progress_days
    FOR SELECT TO energycam_app USING (true);
CREATE POLICY dash_read_progress  ON public.progress_days
    FOR SELECT TO energycam_dashboard USING (true);

-- To check, after the loop has run ten minutes:
--   SELECT day, code, updated_at FROM public.progress_days ORDER BY day DESC, code;
