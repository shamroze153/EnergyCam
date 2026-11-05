@echo off
rem Pull the latest code without leaving the working conda environment.
rem
rem git is installed in the base environment and not in hfm_energy, so a plain
rem "git pull" from the working environment fails with "not recognized" -- which
rem has now interrupted the same job three times.
rem
rem The obvious fix, installing git into hfm_energy as well, is the one to avoid:
rem conda's git brings a set of Unix utilities with it and puts them ahead of the
rem Windows ones on PATH. A shadowed "find" has already cost an afternoon on this
rem project, when "find /c /v" stopped meaning what it means on Windows and went
rem off to search the whole C: drive instead. So this finds git rather than
rem installing another copy of it.

setlocal
cd /d "%~dp0"

where git >nul 2>&1
if %errorlevel%==0 (
    git pull origin main
    goto :eof
)

for %%D in (
    "%CONDA_PREFIX%\..\..\Library\bin"
    "%CONDA_PREFIX%\Library\bin"
    "%USERPROFILE%\anaconda3\Library\bin"
    "%USERPROFILE%\miniconda3\Library\bin"
    "C:\ProgramData\anaconda3\Library\bin"
    "C:\ProgramData\miniconda3\Library\bin"
    "C:\Program Files\Git\cmd"
) do (
    if exist "%%~D\git.exe" (
        echo Using %%~D\git.exe
        "%%~D\git.exe" pull origin main
        goto :eof
    )
)

echo.
echo Could not find git.exe anywhere this script knows to look.
echo Fall back to the base environment:
echo.
echo     conda deactivate
echo     git pull origin main
echo     conda activate hfm_energy
echo.
