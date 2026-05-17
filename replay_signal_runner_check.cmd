@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB replay signal runner smoke check
echo ============================================================
echo.
echo This inserts dummy candles, previews replay signals, inserts dummy research signals, then cleans them up.
echo It does not start the bot, does not connect to a broker, and does not trade.
echo.

python tools\replay_signal_runner_check.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Replay signal runner check failed. Copy the output above and send it.
echo.
pause
exit /b 1
