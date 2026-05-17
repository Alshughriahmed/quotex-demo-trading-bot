@echo off
setlocal
cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB guarded replay research workflow
echo ============================================================
echo.
echo This workflow is for real historical candle CSV files only.
echo It does not start the bot, does not connect to a broker, and does not trade.
echo.
echo Step 1: CSV inventory
python tools\replay_csv_inventory.py
if errorlevel 1 goto error

echo.
echo Step 2: candle import dry-run
python tools\import_replay_candles.py
if errorlevel 1 goto error

echo.
set /p IMPORT_CONFIRM=Type IMPORT to import replay candles: 
if /I not "%IMPORT_CONFIRM%"=="IMPORT" goto cancel

python tools\import_replay_candles.py --yes
if errorlevel 1 goto error

echo.
echo Step 3: replay signal dry-run
python tools\run_replay_signals.py --timeframe 60 --duration 60
if errorlevel 1 goto error

echo.
set /p SIGNAL_CONFIRM=Type SIGNALS to insert replay research signals: 
if /I not "%SIGNAL_CONFIRM%"=="SIGNALS" goto cancel

python tools\run_replay_signals.py --timeframe 60 --duration 60 --yes
if errorlevel 1 goto error

echo.
echo Step 4: outcome evaluation dry-run
python tools\evaluate_replay_outcomes.py --payout 0.80
if errorlevel 1 goto error

echo.
set /p OUTCOME_CONFIRM=Type OUTCOMES to insert replay research outcomes: 
if /I not "%OUTCOME_CONFIRM%"=="OUTCOMES" goto cancel

python tools\evaluate_replay_outcomes.py --payout 0.80 --yes
if errorlevel 1 goto error

echo.
echo Step 5: replay research report
python tools\replay_research_report.py
if errorlevel 1 goto error

echo.
echo Workflow finished.
echo.
pause
exit /b 0

:cancel
echo.
echo Workflow cancelled by user. No further steps were run.
echo.
pause
exit /b 0

:error
echo.
echo Replay research workflow failed. Copy the output above and send it.
echo.
pause
exit /b 1
