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

rem Which address to type into a phone. Streamlit prints a Network URL of
rem its own, but this laptop sits on two networks -- the cable to the camera
rem VLAN and the office WiFi -- and Streamlit picks one without knowing
rem which. When it picks the camera VLAN the address it prints is one no
rem phone can reach, and the obvious conclusion is that the dashboard does
rem not work on a phone. It does.
python phone_url.py

echo Starting the dashboard. It opens in your browser. Ctrl+C to stop.
echo.
streamlit run rooms_dashboard.py %*
