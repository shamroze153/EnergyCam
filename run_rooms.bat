@echo off
rem Pull the latest code, then watch the rooms. Run from the Anaconda Prompt.
rem
rem Three commands were needed for this, in an order that mattered: git lives
rem in the base environment and cv2 lives in hfm_energy, so pulling after
rem activating failed and running before activating failed. Getting it wrong
rem cost a round trip each time, which is a daft thing to spend attention on
rem several times a day.

setlocal
cd /d "%~dp0"

call "%~dp0pull.bat"
if errorlevel 1 (
    echo.
    echo Could not pull. Carrying on with the code already here.
)

where conda >nul 2>&1
if errorlevel 1 (
    echo.
    echo conda is not on PATH. Open the Anaconda Prompt and run this from there.
    exit /b 1
)

call conda activate hfm_energy
if errorlevel 1 (
    echo.
    echo Could not activate hfm_energy.
    exit /b 1
)

echo.
echo Watching the rooms. Ctrl+C to stop.
echo.
python room_loop.py %*
