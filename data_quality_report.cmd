@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB data quality report
echo ============================================================
echo.

python tools\data_quality_report.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Data quality report found a problem or failed.
echo Copy the output above and send it for review.
echo.
pause
exit /b 1
