-- The seven months before June 2025, both 140-H connections.
-- Typed from the same two K-Electric billing summaries as 07 (dated 10
-- November 2026), which go back to November 2024; 07 stopped at June 2025.
-- energycam_app may insert bills already (07's grants), so the loop's
-- machine ran this on 20 Nov 2026; running it again changes nothing.

BEGIN;

-- gf_basement  (account 0400006377759)
INSERT INTO public.meter_bills (meter, period_start, period_end, units, amount_rs, note) VALUES
  ('gf_basement', DATE '2024-11-01', DATE '2024-11-30', 12827, 1112313.30, NULL),
  ('gf_basement', DATE '2024-12-01', DATE '2024-12-31',  9702,  836724.20, NULL),
  ('gf_basement', DATE '2025-01-01', DATE '2025-01-31',  5006,  399779.10, NULL),
  ('gf_basement', DATE '2025-02-01', DATE '2025-02-28',  5317,  378975.03, NULL),
  ('gf_basement', DATE '2025-03-01', DATE '2025-03-31',  6935,  486069.85, NULL),
  ('gf_basement', DATE '2025-04-01', DATE '2025-04-30',  7991,  571503.07, NULL),
  ('gf_basement', DATE '2025-05-01', DATE '2025-05-31', 12961,  869350.40, NULL)
ON CONFLICT (meter, period_start, period_end) DO UPDATE
  SET units = EXCLUDED.units, amount_rs = EXCLUDED.amount_rs;

-- first_cafe  (account 0400006377837)
INSERT INTO public.meter_bills (meter, period_start, period_end, units, amount_rs, note) VALUES
  ('first_cafe', DATE '2024-11-01', DATE '2024-11-30', 10666,  925797.12, NULL),
  ('first_cafe', DATE '2024-12-01', DATE '2024-12-31',  6248,  565824.22, NULL),
  ('first_cafe', DATE '2025-01-01', DATE '2025-01-31',  2392,  211755.61, NULL),
  ('first_cafe', DATE '2025-02-01', DATE '2025-02-28',  2942,  217883.48, NULL),
  ('first_cafe', DATE '2025-03-01', DATE '2025-03-31',  4247,  316497.28, NULL),
  ('first_cafe', DATE '2025-04-01', DATE '2025-04-30',  5448,  413514.18, NULL),
  ('first_cafe', DATE '2025-05-01', DATE '2025-05-31',  6538,  461567.45, NULL)
ON CONFLICT (meter, period_start, period_end) DO UPDATE
  SET units = EXCLUDED.units, amount_rs = EXCLUDED.amount_rs;

COMMIT;
