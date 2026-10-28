# Database setup and credentials

This folder replaces the previous arrangement, in which every part of EnergyCam
connected with the same full-access database password. It addresses item **S3** of the
security review, and closes one issue we found ourselves while implementing it.

## Run order

| Step | File | Who runs it | When |
|------|------|-------------|------|
| 1 | `01_schema.sql` | project owner, Supabase SQL editor | once, before first start |
| 2 | `02_roles.sql` | project owner | once, after step 1 |
| 3 | — | you | put each new connection string in its own place (table below) |
| 4 | `03_rotate.sql` | project owner | once everything runs on the new roles |

`one_time_upgrade.sql` is the older migration for installations that predate this
change. It is unrelated to the roles.

## Which credential goes where

Each component gets its own role and its own connection string. The variable is still
called `DATABASE_URL` in every location, so no code changes — only the value differs.

| Component | Lives on | Role | What it may do |
|-----------|----------|------|----------------|
| `unified_system.py` | camera PC / DVR server | `energycam_app` | INSERT and DELETE rows; read only the `timestamp` column. **Cannot create, alter or drop anything.** |
| `dashboard.py` | Streamlit Cloud | `energycam_dashboard` | SELECT on `logs` only. Cannot write. Cannot see `heartbeat`. |
| `heartbeat_watchdog.py` | a different machine | `energycam_watchdog` | SELECT on `heartbeat` only. |
| `.github/workflows/keepalive.yml` | GitHub Actions | `energycam_keepalive` | SELECT on `heartbeat` only. |

Two deliberate choices in that table:

**The camera system cannot change the schema.** It used to run `CREATE TABLE` on every
start, which meant the credential sitting on an on-site PC could alter the database.
Schema changes now live in `01_schema.sql` and are applied by an administrator.

**The most exposed credential has the least to reach.** The keep-alive secret is stored
in a *public* repository's Actions secrets, so it is the one most likely to be seen by
someone outside the team. It is therefore pointed at `heartbeat`, which holds nothing
but timestamps — no room names, no occupancy, no counts. Previously it counted rows in
`logs`. If that credential ever leaks, it reveals only that the system was running.

## Also fixed here: the public REST API

Supabase publishes every table in the `public` schema through PostgREST, reachable with
the project's anon key. With Row Level Security disabled, occupancy history could be
read from a browser without the database password at all.

`02_roles.sql` enables RLS on both tables and grants policies only to the four service
roles, so `anon` and `authenticated` get nothing. **This was not raised in the security
review; we found it while implementing S3 and are reporting it rather than quietly
fixing it.**

## Connection string format

Direct connection:

    postgresql://<role>:<password>@db.<project-ref>.supabase.co:5432/postgres

Through the session pooler, Supabase expects the project reference in the username:

    postgresql://<role>.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres

Confirm the exact host and username format on the project's *Connect* page before
rolling these out — Supabase has changed it in the past. Every string must keep
`sslmode=require`, which the code already forces.

## Verifying the result

Run these after step 2 and keep the output with the security review:

```sql
-- who can do what
SELECT grantee, table_name, privilege_type
  FROM information_schema.table_privileges
 WHERE table_schema = 'public'
 ORDER BY grantee, table_name, privilege_type;

-- row level security is on
SELECT relname, relrowsecurity FROM pg_class
 WHERE relname IN ('logs', 'heartbeat');

-- nothing still connects as the owner
SELECT usename, application_name, client_addr
  FROM pg_stat_activity WHERE datname = current_database();
```

Expected: `energycam_app` holds INSERT and DELETE but no UPDATE and no references to
`CREATE`; `energycam_dashboard` appears only against `logs`; the two read-only roles
appear only against `heartbeat`; `relrowsecurity` is `t` for both tables; and no
application connects as `postgres`.
