-- EnergyCam least-privilege database roles.  Run ONCE as the project owner, after
-- 01_schema.sql.  Addresses security review item S3 (one all-powerful credential
-- shared by every component) and closes the public REST API on these tables.
--
-- BEFORE RUNNING: replace each CHANGE_ME_* below with a long random password, and
-- keep them somewhere safe.  They are the only copy.
--
-- Afterwards every component gets its OWN connection string, and the old shared
-- credential is rotated (see 03_rotate.sql).

-- ---------------------------------------------------------------- 1. the roles
-- Four roles, because the four places this system runs are not equally exposed.
-- The GitHub Actions secret sits in a public repository, so it gets the least.

CREATE ROLE energycam_app        LOGIN PASSWORD 'CHANGE_ME_APP';
CREATE ROLE energycam_dashboard  LOGIN PASSWORD 'CHANGE_ME_DASHBOARD';
CREATE ROLE energycam_watchdog   LOGIN PASSWORD 'CHANGE_ME_WATCHDOG';
CREATE ROLE energycam_keepalive  LOGIN PASSWORD 'CHANGE_ME_KEEPALIVE';

-- They may reach the schema, but hold no rights in it until granted below.
GRANT USAGE ON SCHEMA public TO
    energycam_app, energycam_dashboard, energycam_watchdog, energycam_keepalive;

-- Nothing is inherited by default, and nothing is granted to PUBLIC.
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- ------------------------------------------------- 2. the camera system (write)
-- Writes log rows and heartbeats, and deletes rows past the retention window.
-- PostgreSQL requires SELECT on any column named in a DELETE's WHERE clause, so
-- the timestamp column — and only that column — is readable by this role.
-- No UPDATE: a row that has been logged is never edited.
-- No DDL: this role cannot create, alter or drop anything.

GRANT INSERT                ON public.logs      TO energycam_app;
GRANT INSERT                ON public.heartbeat TO energycam_app;
GRANT DELETE                ON public.logs      TO energycam_app;
GRANT DELETE                ON public.heartbeat TO energycam_app;
GRANT SELECT (timestamp)    ON public.logs      TO energycam_app;
GRANT SELECT (timestamp)    ON public.heartbeat TO energycam_app;
-- SERIAL primary keys need their sequence.
GRANT USAGE, SELECT ON SEQUENCE public.logs_id_seq      TO energycam_app;
GRANT USAGE, SELECT ON SEQUENCE public.heartbeat_id_seq TO energycam_app;

-- ----------------------------------------------------- 3. the dashboard (read)
-- Streamlit Cloud. Reads room history only; never writes, never sees heartbeat.
GRANT SELECT ON public.logs TO energycam_dashboard;

-- ------------------------------------------------------ 4. the watchdog (read)
-- Runs on a different machine and only needs to know when the last heartbeat was.
GRANT SELECT ON public.heartbeat TO energycam_watchdog;

-- ----------------------------------------------- 5. the keep-alive (read, least)
-- This credential lives in a PUBLIC GitHub repository's Actions secrets, so it is
-- the most exposed one we hold. It is therefore pointed at the heartbeat table,
-- which contains nothing but timestamps — no room names, no occupancy, no counts.
-- If it ever leaks, it reveals only that the system was alive.
GRANT SELECT ON public.heartbeat TO energycam_keepalive;

-- ------------------------------------------------- 6. close the public REST API
-- Supabase exposes every table in `public` through PostgREST to the `anon` and
-- `authenticated` roles. Row Level Security with no policy for those roles shuts
-- that door, so the anon key alone cannot read occupancy data from a browser.
-- This was not in the security review; we raise it ourselves.

ALTER TABLE public.logs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.heartbeat ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.logs      FROM anon, authenticated;
REVOKE ALL ON public.heartbeat FROM anon, authenticated;

-- RLS applies to our roles too, so each one needs an explicit policy. `anon` and
-- `authenticated` get none, which is the point.
CREATE POLICY app_insert_logs  ON public.logs      FOR INSERT TO energycam_app       WITH CHECK (true);
CREATE POLICY app_delete_logs  ON public.logs      FOR DELETE TO energycam_app       USING (true);
CREATE POLICY app_read_logs    ON public.logs      FOR SELECT TO energycam_app       USING (true);
CREATE POLICY app_insert_hb    ON public.heartbeat FOR INSERT TO energycam_app       WITH CHECK (true);
CREATE POLICY app_delete_hb    ON public.heartbeat FOR DELETE TO energycam_app       USING (true);
CREATE POLICY app_read_hb      ON public.heartbeat FOR SELECT TO energycam_app       USING (true);
CREATE POLICY dash_read_logs   ON public.logs      FOR SELECT TO energycam_dashboard USING (true);
CREATE POLICY watch_read_hb    ON public.heartbeat FOR SELECT TO energycam_watchdog  USING (true);
CREATE POLICY keep_read_hb     ON public.heartbeat FOR SELECT TO energycam_keepalive USING (true);

-- ------------------------------------------------------------- 7. what to check
-- Run these after applying, and keep the output with the security review:
--   SELECT grantee, table_name, privilege_type FROM information_schema.table_privileges
--    WHERE table_schema='public' ORDER BY grantee, table_name, privilege_type;
--   SELECT relname, relrowsecurity FROM pg_class
--    WHERE relname IN ('logs','heartbeat');
