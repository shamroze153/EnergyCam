-- Rotating the old shared credential.  Run as the project owner AFTER 02_roles.sql
-- has been applied and all four components are confirmed working on their own roles.
--
-- Why: the original DATABASE_URL was a single full-access credential that has been
-- copied into three third-party systems (the office PC's .env, Streamlit Cloud
-- secrets, and GitHub Actions secrets). Once a secret has travelled that far it must
-- be treated as exposed, whether or not a leak is known. Security review item S3.
--
-- Order matters. Do not rotate until the new roles are live, or the system stops.

-- 1. Confirm nothing still uses the old credential.  Each component should appear
--    under its own role name here; `postgres` should not appear at all.
SELECT usename, application_name, client_addr, backend_start
  FROM pg_stat_activity
 WHERE datname = current_database()
 ORDER BY backend_start DESC;

-- 2. Change the old password.  Replace with a long random value and store it in the
--    password manager, not in a chat message or a repository.
-- ALTER ROLE postgres WITH PASSWORD 'CHANGE_ME_NEW_OWNER_PASSWORD';

-- 3. Remove the old connection string from everywhere it was copied:
--      - the camera PC's .env                 -> replace with the energycam_app URL
--      - Streamlit Cloud app secrets          -> replace with energycam_dashboard
--      - GitHub Actions repository secrets    -> replace with energycam_keepalive
--      - the watchdog machine's .env          -> replace with energycam_watchdog
--    Delete the old value from each place rather than leaving it unused.

-- 4. Re-run the check in step 1 after a day. If `postgres` still connects from an
--    application, something was missed.

-- Routine rotation of the four service roles (every 6 months, or on staff change):
-- ALTER ROLE energycam_app       WITH PASSWORD 'CHANGE_ME';
-- ALTER ROLE energycam_dashboard WITH PASSWORD 'CHANGE_ME';
-- ALTER ROLE energycam_watchdog  WITH PASSWORD 'CHANGE_ME';
-- ALTER ROLE energycam_keepalive WITH PASSWORD 'CHANGE_ME';
