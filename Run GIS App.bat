@echo off
title GIS Shapefile Generator
cd /d "%~dp0"
echo ============================================================
echo   GIS Shapefile Generator
echo.
echo   Starting the local engine...
echo   A browser tab will open at  http://127.0.0.1:5000/
echo   Use THAT tab (not any preview window).
echo   Keep this black window OPEN while you work. Close it to stop.
echo ============================================================
echo.

rem Prefer the Windows "py" launcher (avoids the Microsoft Store python stub).
where py >nul 2>nul
if %errorlevel%==0 (
    py app.py
) else (
    python app.py
)

echo.
echo ------------------------------------------------------------
echo The app has stopped. If you saw an error above, screenshot it.
echo ------------------------------------------------------------
pause
