@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB replay signal-only strategy runner
echo ============================================================
echo.
echo This reads research_market_candles and creates research_signals only after confirmation.
echo It does not start the bot, does not connect to a broker, and does not trade.
echo.

python tools\run_replay_signals.py --timeframe 60 --duration 60
if errorlevel 1 goto error

echo.
set /p CONFIRM=Type RUN to insert replay research signals: 
if /I not "%CONFIRM%"=="RUN" goto cancel

python tools\run_replay_signals.py --timeframe 60 --duration 60 --yes
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:cancel
echo.
echo Replay signal run cancelled. No research signals were inserted.
echo.
pause
exit /b 0

:error
echo.
echo Replay signal runner failed. Copy the output above and send it.
echo.
pause
exit /b 1
