@echo off
cd /d C:\hfm_energy_project
call conda activate hfm_energy

:loop
echo [%date% %time%] System start ho raha hai...
python unified_system.py
echo [%date% %time%] System band ho gaya, 5 second mein dobara start hoga...
timeout /t 5
goto loop