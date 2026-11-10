-- Seventeen months of real bills, and somewhere to put the solar.
-- Run ONCE as the project owner, after sql/06_meters.sql.
--
-- Typed from the two K-Electric billing summaries dated 10 November 2026.
-- These are the first measured numbers this system has about money: until
-- now the tariff was an assumption in rooms.yaml and the consumption was
-- inferred from cameras. A year of bills settles both, and it settles them
-- today rather than after a year of waiting.
--
-- Two things in this data are worth somebody checking with K-Electric, and
-- both are flagged in the notes below rather than quietly loaded.

BEGIN;

-- first_cafe  (account 0400006377837)
INSERT INTO public.meter_bills (meter, period_start, period_end, units, amount_rs, note) VALUES
  ('first_cafe', DATE '2025-06-01', DATE '2025-06-30', 4645, 310491.90, NULL),
  ('first_cafe', DATE '2025-07-01', DATE '2025-07-31', 3389, 209310.03, NULL),
  ('first_cafe', DATE '2025-08-01', DATE '2025-08-31', 3585, 268808.24, NULL),
  ('first_cafe', DATE '2025-09-01', DATE '2025-09-30', 3901, 276696.76, NULL),
  ('first_cafe', DATE '2025-10-01', DATE '2025-10-31', 3805, 281981.21, NULL),
  ('first_cafe', DATE '2025-11-01', DATE '2025-11-30', 3592, 266624.65, NULL),
  ('first_cafe', DATE '2025-12-01', DATE '2025-12-31', 2009, 167091.40, NULL),
  ('first_cafe', DATE '2026-01-01', DATE '2026-01-31', 1600, 140626.52, NULL),
  ('first_cafe', DATE '2026-02-01', DATE '2026-02-28', 1133, 115554.99, NULL),
  ('first_cafe', DATE '2026-03-01', DATE '2026-03-31', 2130, 184190.86, NULL),
  ('first_cafe', DATE '2026-04-01', DATE '2026-04-30', 2868, 232441.32, NULL),
  ('first_cafe', DATE '2026-05-01', DATE '2026-05-31', 5044, 379344.16, NULL),
  ('first_cafe', DATE '2026-06-01', DATE '2026-06-30', 3277, 259766.74, NULL),
  ('first_cafe', DATE '2026-07-01', DATE '2026-07-31', 41145, 2731004.20, 'QUERY THIS. 41145 units is 149% of what a 37 kW connection can deliver in 31 days, and seven times the months either side. Either a catch-up for earlier estimated reads, a meter fault, or a billing error worth about Rs 2.4 million.'),
  ('first_cafe', DATE '2026-08-01', DATE '2026-08-31', 6332, 474510.95, NULL),
  ('first_cafe', DATE '2026-09-01', DATE '2026-09-30', 5986, 594336.61, NULL),
  ('first_cafe', DATE '2026-10-01', DATE '2026-10-31', 7440, 577293.61, NULL)
ON CONFLICT (meter, period_start, period_end) DO UPDATE
  SET units = EXCLUDED.units, amount_rs = EXCLUDED.amount_rs,
      note = EXCLUDED.note;

-- gf_basement  (account 0400006377759)
INSERT INTO public.meter_bills (meter, period_start, period_end, units, amount_rs, note) VALUES
  ('gf_basement', DATE '2025-06-01', DATE '2025-06-30', 13783, 890231.67, 'Above the 19 kW ceiling for this many days. Either the sanctioned load on file is wrong, or the connection was overdrawn.'),
  ('gf_basement', DATE '2025-07-01', DATE '2025-07-31', 12781, 810951.71, NULL),
  ('gf_basement', DATE '2025-08-01', DATE '2025-08-31', 11947, 845343.16, NULL),
  ('gf_basement', DATE '2025-09-01', DATE '2025-09-30', 10894, 713893.09, NULL),
  ('gf_basement', DATE '2025-10-01', DATE '2025-10-31', 10793, 766000.72, NULL),
  ('gf_basement', DATE '2025-11-01', DATE '2025-11-30', 13633, 972322.98, NULL),
  ('gf_basement', DATE '2025-12-01', DATE '2025-12-31', 10862, 798735.21, NULL),
  ('gf_basement', DATE '2026-01-01', DATE '2026-01-31', 9980, 727289.93, NULL),
  ('gf_basement', DATE '2026-02-01', DATE '2026-02-28', 8979, 678216.02, NULL),
  ('gf_basement', DATE '2026-03-01', DATE '2026-03-31', 9054, 711424.12, NULL),
  ('gf_basement', DATE '2026-04-01', DATE '2026-04-30', 11015, 855795.89, NULL),
  ('gf_basement', DATE '2026-05-01', DATE '2026-05-31', 16256, 1202388.76, 'Above the 19 kW ceiling for this many days. Either the sanctioned load on file is wrong, or the connection was overdrawn.'),
  ('gf_basement', DATE '2026-06-01', DATE '2026-06-30', 10809, 783327.24, NULL),
  ('gf_basement', DATE '2026-07-01', DATE '2026-07-31', 9212, 676870.59, NULL),
  ('gf_basement', DATE '2026-08-01', DATE '2026-08-31', 11972, 854236.07, NULL),
  ('gf_basement', DATE '2026-09-01', DATE '2026-09-30', 10430, 780623.47, NULL),
  ('gf_basement', DATE '2026-10-01', DATE '2026-10-31', 11623, 887174.92, NULL)
ON CONFLICT (meter, period_start, period_end) DO UPDATE
  SET units = EXCLUDED.units, amount_rs = EXCLUDED.amount_rs,
      note = EXCLUDED.note;

-- ------------------------------------------------- the solar array
-- Generation belongs to the array, not to a meter. The array feeds the
-- ground floor and basement connection, so that meter's units are what was
-- left to buy after the panels had contributed -- which is why a bright day
-- reads low there for reasons that have nothing to do with anybody
-- switching anything off. Recording generation separately is what lets the
-- two be told apart.
CREATE TABLE IF NOT EXISTS public.solar_daily (
    id      BIGSERIAL PRIMARY KEY,
    taken   TIMESTAMPTZ NOT NULL,
    kwh     NUMERIC(10,2) NOT NULL,
    note    TEXT,
    CONSTRAINT one_solar_a_day UNIQUE (taken)
);
CREATE INDEX IF NOT EXISTS solar_daily_when ON public.solar_daily (taken DESC);

GRANT SELECT, INSERT, UPDATE ON public.solar_daily TO energycam_app;
GRANT USAGE, SELECT ON SEQUENCE public.solar_daily_id_seq TO energycam_app;
GRANT SELECT ON public.solar_daily TO energycam_dashboard;
ALTER TABLE public.solar_daily ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.solar_daily FROM anon, authenticated;
DROP POLICY IF EXISTS app_rw_solar  ON public.solar_daily;
DROP POLICY IF EXISTS dash_rd_solar ON public.solar_daily;
CREATE POLICY app_rw_solar  ON public.solar_daily
    FOR ALL    TO energycam_app       USING (true) WITH CHECK (true);
CREATE POLICY dash_rd_solar ON public.solar_daily
    FOR SELECT TO energycam_dashboard USING (true);

COMMIT;

-- What these bills say, for whoever reads this file later:
--   Rs 73.38 per unit across both meters over sixteen clean months, against
--   the Rs 55 that rooms.yaml assumed. Every money figure the dashboard has
--   shown so far is understated by about a third.
--   Rs 16.0 million over the last twelve months across the two connections.
