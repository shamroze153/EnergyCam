-- The two K-Electric meters at 140-H. Run ONCE as the project owner.
--
-- Why this matters more than it looks: every rupee on the dashboard today
-- rests on two guesses -- 1.2 kW per unit and Rs 55 per kWh -- and the page
-- says so rather than calling them a bill. A meter reading is the first
-- measured number in the whole system. With a month of them beside the hours
-- rooms sat empty and cooled, the kilowatts stop being assumed; with the
-- bills, so does the tariff.
--
-- Two things about these particular meters have to be carried in the data
-- rather than remembered by whoever set it up:
--
--   The GF + basement meter has the solar array behind it. Its reading is
--   what the building drew from the grid AFTER the panels had contributed,
--   so a sunny day reads low for a reason that has nothing to do with
--   anybody switching an air conditioner off. That meter cannot be used on
--   its own to show a saving. The first floor + cafe meter has no solar and
--   is the clean one.
--
--   A reading is taken by a person at about the same time each day, not at
--   midnight. So a day here runs from one reading to the next, and the
--   night -- which is the part worth measuring -- sits inside one period
--   rather than being split across two. Everything downstream lines its
--   occupancy hours up to these timestamps instead of to the calendar.

-- -------------------------------------------------------- 1. the meters
CREATE TABLE IF NOT EXISTS public.meters (
    code        TEXT PRIMARY KEY,          -- 'gf_basement' | 'first_cafe'
    label       TEXT        NOT NULL,
    covers      TEXT        NOT NULL,
    account     TEXT,                      -- the K-Electric account number
    meter_no    TEXT,                      -- the number stamped on the meter
    sanctioned_kw NUMERIC(6,1),            -- the connection's sanctioned load
    behind_solar BOOLEAN    NOT NULL DEFAULT FALSE,
    note        TEXT
);
-- The account and meter numbers are here so a bill can be matched to a meter
-- without anybody having to remember which is which. The sanctioned load is
-- here because it is a hard ceiling: a day cannot draw more than the load
-- times twenty-four hours, so a reading above that is a mistyped digit
-- rather than a remarkable day.

INSERT INTO public.meters
  (code, label, covers, account, meter_no, sanctioned_kw, behind_solar, note)
VALUES
  ('gf_basement', 'Ground floor + basement',
   'Ground floor and basement',
   '0400006377759', 'TY75237', 19.0, TRUE,
   'The solar array feeds this meter, so its units are what was drawn from '
   'the grid after the panels. A sunny day reads low for reasons unrelated '
   'to anyone switching anything off, and this meter alone cannot show a '
   'saving. Tariff A-2B, time-of-use. October 2026 billed fixed charges on '
   'an MDI of 38 kW against a sanctioned 19 -- see the analysis notes.'),
  ('first_cafe',  'First floor + cafe',
   'First floor, and the cafe on the second',
   '0400006377837', 'TU09825', 37.0, FALSE,
   'No solar behind this one, so it is the meter to trust when asking '
   'whether a change in behaviour changed consumption. Twice the sanctioned '
   'load of the other, which the cafe''s equipment explains.')
ON CONFLICT (code) DO UPDATE
  SET label = EXCLUDED.label, covers = EXCLUDED.covers,
      account = EXCLUDED.account, meter_no = EXCLUDED.meter_no,
      sanctioned_kw = EXCLUDED.sanctioned_kw,
      behind_solar = EXCLUDED.behind_solar, note = EXCLUDED.note;

-- ------------------------------------------------------- 2. the readings
-- Either form is accepted, because both are things a person actually has in
-- front of them: the cumulative number on the meter's face, or the units for
-- the day from the K-Electric app. Storing which one was given, rather than
-- quietly converting, is what makes a mistyped digit findable later.
CREATE TABLE IF NOT EXISTS public.meter_readings (
    id        BIGSERIAL PRIMARY KEY,
    meter     TEXT        NOT NULL REFERENCES public.meters(code),
    taken     TIMESTAMPTZ NOT NULL,
    reading   NUMERIC(12,2),      -- the cumulative figure on the meter
    units     NUMERIC(10,2),      -- or the units since the last reading
    max_temp  NUMERIC(4,1),       -- the day's high, because weather drives AC
    note      TEXT,
    CONSTRAINT one_or_the_other CHECK (reading IS NOT NULL OR units IS NOT NULL),
    CONSTRAINT one_a_day UNIQUE (meter, taken)
);
CREATE INDEX IF NOT EXISTS meter_readings_when
    ON public.meter_readings (meter, taken DESC);

-- ---------------------------------------------------------- 3. the bills
-- One a month, and the only place a real tariff ever appears. Until one is
-- here, Rs/kWh on the dashboard is the assumption in rooms.yaml.
CREATE TABLE IF NOT EXISTS public.meter_bills (
    id           BIGSERIAL PRIMARY KEY,
    meter        TEXT NOT NULL REFERENCES public.meters(code),
    period_start DATE NOT NULL,
    period_end   DATE NOT NULL,
    units        NUMERIC(10,2) NOT NULL,
    amount_rs    NUMERIC(12,2) NOT NULL,
    note         TEXT,
    CONSTRAINT sane_period CHECK (period_end > period_start),
    CONSTRAINT one_per_period UNIQUE (meter, period_start, period_end)
);

-- ---------------------------------------------------------- 4. who may
-- The camera machine may write these. That is a deliberate exception to the
-- rule that it cannot read room data: the reason for that rule is that a
-- machine in a corridor cupboard should not be able to reconstruct who was
-- in which room, and a meter reading says nothing about anybody. The
-- dashboard reads all three.
GRANT SELECT, INSERT, UPDATE ON public.meter_readings TO energycam_app;
GRANT SELECT, INSERT, UPDATE ON public.meter_bills    TO energycam_app;
GRANT SELECT                 ON public.meters         TO energycam_app;
GRANT USAGE, SELECT ON SEQUENCE public.meter_readings_id_seq TO energycam_app;
GRANT USAGE, SELECT ON SEQUENCE public.meter_bills_id_seq    TO energycam_app;

GRANT SELECT ON public.meters         TO energycam_dashboard;
GRANT SELECT ON public.meter_readings TO energycam_dashboard;
GRANT SELECT ON public.meter_bills    TO energycam_dashboard;

ALTER TABLE public.meters         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meter_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meter_bills    ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.meters, public.meter_readings, public.meter_bills
    FROM anon, authenticated;

DROP POLICY IF EXISTS app_rw_readings   ON public.meter_readings;
DROP POLICY IF EXISTS app_rw_bills      ON public.meter_bills;
DROP POLICY IF EXISTS app_read_meters   ON public.meters;
DROP POLICY IF EXISTS dash_read_readings ON public.meter_readings;
DROP POLICY IF EXISTS dash_read_bills    ON public.meter_bills;
DROP POLICY IF EXISTS dash_read_meters   ON public.meters;

CREATE POLICY app_rw_readings    ON public.meter_readings
    FOR ALL    TO energycam_app       USING (true) WITH CHECK (true);
CREATE POLICY app_rw_bills       ON public.meter_bills
    FOR ALL    TO energycam_app       USING (true) WITH CHECK (true);
CREATE POLICY app_read_meters    ON public.meters
    FOR SELECT TO energycam_app       USING (true);
CREATE POLICY dash_read_readings ON public.meter_readings
    FOR SELECT TO energycam_dashboard USING (true);
CREATE POLICY dash_read_bills    ON public.meter_bills
    FOR SELECT TO energycam_dashboard USING (true);
CREATE POLICY dash_read_meters   ON public.meters
    FOR SELECT TO energycam_dashboard USING (true);
