@echo off
setlocal
cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB DEMO scanner status
echo ============================================================
echo.
python tools\scanner_state.py --status
echo.
pause
