@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB disable automatic DEMO buying
echo ============================================================
echo.
echo This writes auto_buy_enabled=false to the local database.
echo It does not print secrets and does not change GitHub.
echo.

python tools\disable_auto_buy.py
if errorlevel 1 goto error

echo.
echo Running data quality report after safety guard...
python tools\data_quality_report.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Auto-buy disable guard failed. Copy the output above and send it for review.
echo.
pause
exit /b 1
