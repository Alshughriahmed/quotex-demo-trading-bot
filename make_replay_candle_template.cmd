@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB replay candle CSV template
echo ============================================================
echo.
echo This creates a CSV template in bot\external_inputs.
echo It does not import data, does not start the bot, and does not trade.
echo.

python tools\make_replay_candle_template.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Replay candle template creation failed. Copy the output above and send it.
echo.
pause
exit /b 1
