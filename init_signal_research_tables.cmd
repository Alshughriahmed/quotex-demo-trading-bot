@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB signal-only research tables initializer
echo ============================================================
echo.
echo This creates research_* tables only.
echo It does not start the bot, does not trade, and does not print secrets.
echo.

python tools\init_signal_research_tables.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Signal research table initialization failed. Copy the output above and send it.
echo.
pause
exit /b 1
