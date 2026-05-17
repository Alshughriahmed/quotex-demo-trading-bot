@echo off
setlocal

cd /d "%~dp0"

echo.
echo ============================================================
echo  QTB project health check
echo ============================================================
echo.
echo This runs safe local checks only.
echo It does not start the bot, does not trade, and does not print secrets.
echo.

echo [1/5] Git status
git status --short
if errorlevel 1 goto error

echo.
echo [2/5] Recent commits
git log -5 --oneline
if errorlevel 1 goto error

echo.
echo [3/5] Python syntax check
python -m compileall -q bot
if errorlevel 1 goto error

echo.
echo [4/5] Data quality report
cd /d "%~dp0bot"
python tools\data_quality_report.py
if errorlevel 1 goto error

echo.
echo [5/5] External dataset inventory
python tools\external_inventory.py
if errorlevel 1 goto error

echo.
echo ============================================================
echo  Health check finished successfully.
echo ============================================================
echo.
pause
exit /b 0

:error
echo.
echo ============================================================
echo  Health check failed. Copy the output above and send it.
echo ============================================================
echo.
pause
exit /b 1
