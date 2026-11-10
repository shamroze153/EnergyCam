-- Let the dashboard write a meter reading. Run ONCE, after 06 and 07.
--
-- Until now a reading could only be entered from a command line on one
-- machine by one person, which means the day that person is on leave is a
-- day with no reading, and a gap in a daily series is worth more than one
-- missing number: it breaks every comparison that crosses it.
--
-- So the page gets a form, and the read-only role it connects as gets the
-- narrowest write that allows: inserting and correcting meter readings and
-- solar generation, and nothing else. It still cannot touch room_events,
-- so the page remains unable to rewrite who was in which room.

GRANT SELECT, INSERT, UPDATE ON public.meter_readings TO energycam_dashboard;
GRANT SELECT, INSERT, UPDATE ON public.solar_daily    TO energycam_dashboard;
GRANT USAGE, SELECT ON SEQUENCE public.meter_readings_id_seq
    TO energycam_dashboard;
GRANT USAGE, SELECT ON SEQUENCE public.solar_daily_id_seq
    TO energycam_dashboard;

DROP POLICY IF EXISTS dash_write_readings ON public.meter_readings;
DROP POLICY IF EXISTS dash_write_solar    ON public.solar_daily;
CREATE POLICY dash_write_readings ON public.meter_readings
    FOR ALL TO energycam_dashboard USING (true) WITH CHECK (true);
CREATE POLICY dash_write_solar    ON public.solar_daily
    FOR ALL TO energycam_dashboard USING (true) WITH CHECK (true);
