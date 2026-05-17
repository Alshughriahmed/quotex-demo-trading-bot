@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB scanner source guard
echo ============================================================
echo.
echo This keeps the DEMO scanner stopped when no market data source is configured.
echo It does not print secrets and does not change GitHub.
echo.

python tools\guard_scanner_without_source.py
if errorlevel 1 goto error

echo.
echo Running data quality report after guard check...
python tools\data_quality_report.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Guard check failed. Copy the output above and send it for review.
echo.
pause
exit /b 1
