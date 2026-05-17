@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB simulated paper trade generator
echo ============================================================
echo.
echo This creates simulated DEMO records for testing exports and reports.
echo These are NOT real strategy results.
echo.

python tools\generate_paper_trades.py --count 25
if errorlevel 1 goto error

echo.
echo Now exporting trades to CSV...
python tools\export_trades.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Paper generation failed. Copy the output above and send it for review.
echo.
pause
exit /b 1
