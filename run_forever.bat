@echo off
rem Keep the room loop running, and bring it back when it stops.
rem
rem This is the always-on version. The ordinary run_rooms.bat is for a person
rem sitting in front of it: when it stops, they see why. On a machine nobody
rem is watching, a loop that stopped at nine in the evening means the whole
rem night went unrecorded and nothing said so until somebody opened the
rem dashboard the next morning -- which is precisely the window this project
rem exists to measure.
rem
rem So: restart on exit, back off when it keeps failing rather than hammering
rem the recorders and GitHub, and give up only on a configuration error,
rem which restarting cannot fix.

setlocal
cd /d "%~dp0"

set WAIT=10
set TRIES=0

:loop
echo.
echo ===============================================================
echo  starting the room loop at %DATE% %TIME%
echo ===============================================================

call "%~dp0pull.bat"

where conda >nul 2>&1
if errorlevel 1 (
    echo conda is not on PATH. Start this from the Anaconda Prompt,
    echo or from a scheduled task whose program is the Anaconda Prompt.
    exit /b 1
)
call conda activate hfm_energy
if errorlevel 1 (
    echo Could not activate hfm_energy.
    exit /b 1
)

python room_loop.py %*
set CODE=%ERRORLEVEL%

if "%CODE%"=="78" (
    echo.
    echo The loop stopped on a configuration problem, which restarting will
    echo not fix. Read the message above. Nothing else will be tried.
    exit /b 78
)
if "%CODE%"=="0" (
    echo.
    echo The loop exited cleanly. Not restarting.
    exit /b 0
)

set /a TRIES+=1
echo.
echo The loop stopped with code %CODE%. Restart %TRIES% in %WAIT% seconds.
timeout /t %WAIT% /nobreak >nul

rem Back off up to five minutes: a recorder that has stopped answering, or a
rem network that is down, is not helped by being asked every ten seconds.
if %WAIT% LSS 300 set /a WAIT=%WAIT%*2
if %WAIT% GTR 300 set WAIT=300
goto loop
