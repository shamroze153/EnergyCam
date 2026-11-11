@echo off
rem The whole audit, again and again, until Ctrl+C -- for leaving running
rem overnight beside the loop. Each run makes its own field_audit_<time>.zip,
rem so the morning has the whole night in pictures: by day a wrong count,
rem by night every ghost (at night nobody should be there, so anything the
rem detector finds is a chair, a coat or a poster).
rem
rem Run it in a SECOND Anaconda Prompt window. The loop keeps running in
rem the first; this only looks, and changes nothing.
rem
rem     night_audit.bat          every two hours
rem     night_audit.bat 60       every hour

setlocal
cd /d "%~dp0"
set EVERY=%1
if "%EVERY%"=="" set EVERY=120

where conda >nul 2>&1
if errorlevel 1 (
    echo conda is not on PATH. Open the Anaconda Prompt and run this from there.
    exit /b 1
)
call conda activate hfm_energy
if errorlevel 1 (
    echo Could not activate hfm_energy.
    exit /b 1
)

:again
echo.
echo ==== %date% %time% : audit starting ====
python field_audit.py
echo.
echo Next audit in %EVERY% minutes. Ctrl+C to stop.
set /a WAIT=%EVERY%*60
timeout /t %WAIT% /nobreak >nul
goto again
