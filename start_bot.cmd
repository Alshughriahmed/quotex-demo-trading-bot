@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB Telegram DEMO Bot
echo ============================================================
echo.
echo Starting bot from:
echo %cd%
echo.
echo Press Ctrl+C to stop the bot.
echo.

python main.py

echo.
echo Bot process ended.
echo.
pause
