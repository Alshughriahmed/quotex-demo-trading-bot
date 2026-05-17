@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB replay signal outcome evaluator
echo ============================================================
echo.
echo This evaluates research_signals against replay candles only after confirmation.
echo It does not start the bot, does not connect to a broker, and does not trade.
echo.

python tools\evaluate_replay_outcomes.py --payout 0.80
if errorlevel 1 goto error

echo.
set /p CONFIRM=Type EVALUATE to insert replay research outcomes: 
if /I not "%CONFIRM%"=="EVALUATE" goto cancel

python tools\evaluate_replay_outcomes.py --payout 0.80 --yes
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:cancel
echo.
echo Replay outcome evaluation cancelled. No research outcomes were inserted.
echo.
pause
exit /b 0

:error
echo.
echo Replay outcome evaluator failed. Copy the output above and send it.
echo.
pause
exit /b 1
