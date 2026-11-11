@echo off
rem Stop the running loop and start it again, so a change to rooms.yaml
rem takes effect. The loop reads rooms.yaml once, when it starts: rooms
rem added while it runs are never written down until it is restarted --
rem which is how fourteen rooms went unrecorded on 11 November.
rem
rem     restart_loop.bat --evidence      the usual flags go on the end
rem
rem Works from any window, including one Claude is running commands in:
rem it finds the loop by its command line, stops it, waits, activates the
rem hfm_energy environment (OpenCV's DLLs need it) and starts a new loop,
rem minimised, in a window of its own that stays open if it ever fails.

setlocal
cd /d "%~dp0"

powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*room_loop.py*' }; if ($p) { $p | ForEach-Object { Write-Host ('stopping the loop, process ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force } } else { Write-Host 'no loop was running' }"
timeout /t 5 /nobreak >nul

set CONDA_ROOT=%LOCALAPPDATA%\miniconda3
if not exist "%CONDA_ROOT%\Scripts\activate.bat" set CONDA_ROOT=%USERPROFILE%\miniconda3
if not exist "%CONDA_ROOT%\Scripts\activate.bat" set CONDA_ROOT=%USERPROFILE%\anaconda3
if not exist "%CONDA_ROOT%\Scripts\activate.bat" (
    echo Cannot find conda. Start the loop by hand in the Anaconda Prompt:
    echo     run_rooms.bat --evidence
    exit /b 1
)
call "%CONDA_ROOT%\Scripts\activate.bat" hfm_energy
if errorlevel 1 (
    echo Could not activate hfm_energy.
    exit /b 1
)

start "EnergyCam loop" /min cmd /k python room_loop.py %*
echo The loop is running again, minimised, in a window called "EnergyCam loop".
