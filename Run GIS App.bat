@echo off
title GIS Distribution Line Drawing
cd /d "%~dp0"

rem Use the Windows "py" launcher if present, else "python"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)

rem Make sure Python exists
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo Python 3 was not found. Install it from https://www.python.org/downloads/
    echo and tick "Add Python to PATH", then run this again.
    pause
    exit /b 1
)

rem First-time setup: if Flask is missing, install the requirements automatically
%PY% -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo First-time setup: installing required packages. This can take a few minutes...
    echo.
    %PY% -m pip install --upgrade pip
    %PY% -m pip install -r requirements.txt
    echo.
)

echo ============================================================
echo   Starting the app. A browser tab opens at  http://127.0.0.1:5000/
echo   Use THAT tab (not any preview window).
echo   Keep this black window OPEN while you work. Close it to stop.
echo ============================================================
echo.
%PY% app.py

echo.
echo ------------------------------------------------------------
echo The app has stopped. If you saw an error above, screenshot it.
echo ------------------------------------------------------------
pause
