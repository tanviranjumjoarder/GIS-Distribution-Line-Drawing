@echo off
title Install requirements - GIS Distribution Line Drawing
cd /d "%~dp0"

echo ============================================================
echo   Installing the Python packages this app needs:
echo   flask, geopandas, pandas, shapely, pyproj, xlrd, openpyxl, gunicorn
echo   This can take a few minutes the first time. Please wait...
echo ============================================================
echo.

rem Use the Windows "py" launcher if present, else "python"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)

%PY% --version
if errorlevel 1 (
    echo.
    echo Python was not found. Install Python 3 from https://www.python.org/downloads/
    echo and tick "Add Python to PATH", then run this again.
    echo.
    pause
    exit /b 1
)

%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt

echo.
if errorlevel 1 (
    echo ------------------------------------------------------------
    echo Something went wrong during install. Screenshot the message above.
    echo ------------------------------------------------------------
) else (
    echo ------------------------------------------------------------
    echo All set. You can now run "Run GIS App.bat".
    echo ------------------------------------------------------------
)
pause
