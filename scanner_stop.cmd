@echo off
setlocal
cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB stop DEMO scanner
echo ============================================================
echo.
python tools\scanner_state.py --stop
echo.
pause
