@echo off
rem Open the dashboard. Run from the Anaconda Prompt, in its own window:
rem the room loop keeps running in the other one, and both are needed --
rem the loop reads the cameras, this only reads the database.

setlocal
cd /d "%~dp0"

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
echo Starting the dashboard. It opens in your browser. Ctrl+C to stop.
echo.
streamlit run rooms_dashboard.py %*
