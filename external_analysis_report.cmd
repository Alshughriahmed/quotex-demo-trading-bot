@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB external trade analysis report
echo ============================================================
echo.
echo This reads external_* research tables only.
echo It does not start the bot, does not trade, and does not print secrets.
echo.

python tools\external_analysis_report.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo External analysis failed. Copy the output above and send it.
echo.
pause
exit /b 1
