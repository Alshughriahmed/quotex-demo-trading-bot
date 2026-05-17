@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB Telegram DEMO Bot - Safe Mode
echo ============================================================
echo.
echo Starting bot from:
echo %cd%
echo.
echo Safe launcher will enforce auto_buy_enabled=false unless explicitly changed.
echo Press Ctrl+C to stop the bot.
echo.

python start_safe.py

echo.
echo Bot process ended.
echo.
pause
