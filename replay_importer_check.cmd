@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB replay importer smoke check
echo ============================================================
echo.
echo This creates a temporary dummy CSV, dry-runs it, imports it, then cleans it up.
echo It does not start the bot, does not connect to a broker, and does not trade.
echo.

python tools\replay_importer_check.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Replay importer check failed. Copy the output above and send it.
echo.
pause
exit /b 1
