@echo off
cd /d C:\hfm_energy_project
call conda activate hfm_energy

:loop
echo [%date% %time%] System start ho raha hai...
python unified_system.py

rem Exit code 78 means a configuration error (a missing or malformed setting in
rem .env, or the database tables not created yet). Restarting cannot fix that, and
rem a silent five-second loop hides the real problem while repeatedly hammering the
rem database and the mail server. So stop, and wait for a person.
if errorlevel 78 if not errorlevel 79 goto config_error

echo [%date% %time%] System band ho gaya, 5 second mein dobara start hoga...
timeout /t 5
goto loop

:config_error
echo.
echo ============================================================
echo  [%date% %time%] CONFIGURATION ERROR
echo  System dobara start NAHI hoga.
echo  Upar likhi hui baat theek karein (.env file), phir ye
echo  window dobara chalayein.
echo ============================================================
echo.
pause
