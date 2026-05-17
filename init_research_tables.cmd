@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB research tables initializer
echo ============================================================
echo.
echo This prepares separate local tables for external datasets.
echo It does not import files and does not print secrets.
echo.

python tools\init_research_tables.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Research table initialization failed. Copy the output above and send it for review.
echo.
pause
exit /b 1
