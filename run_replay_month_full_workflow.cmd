@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo QTB one-click replay month workflow
echo.
echo This workflow runs locally on your computer only.
echo It does not upload CSV files to GitHub.
echo It does not start the bot, does not connect to a broker, and does not trade.
echo It writes research candles/signals/outcomes only inside bot\data.db.
echo.

set /p "RAWCSV=Raw CSV filename in bot\external_inputs, example DAT_ASCII_USDCAD_M1_202601.csv: "
if "%RAWCSV%"=="" goto missing_raw
set /p "ASSET=Asset, example USD/CAD: "
if "%ASSET%"=="" goto missing_asset
set /p "TIMEFRAME=Timeframe seconds, empty for 60: "
if "%TIMEFRAME%"=="" set "TIMEFRAME=60"
set /p "SOURCEKEY=Source key, example histdata_usdcad_m1_202601: "
if "%SOURCEKEY%"=="" goto missing_source
set /p "DURATION=Duration seconds, empty for 60: "
if "%DURATION%"=="" set "DURATION=60"
set /p "LOOKBACK=Analysis lookback candles, empty for 300: "
if "%LOOKBACK%"=="" set "LOOKBACK=300"
set /p "PAYOUT=Theoretical payout, empty for 0.80: "
if "%PAYOUT%"=="" set "PAYOUT=0.80"

for %%F in ("%RAWCSV%") do set "REPLAYCSV=replay_ready_%%~nF.csv"
set "STRATEGYVERSION=replay_signal_only_v1_lookback_%LOOKBACK%"

echo.
echo Planned local workflow:
echo Raw CSV: bot\external_inputs\%RAWCSV%
echo Replay CSV: bot\external_inputs\%REPLAYCSV%
echo Source key: %SOURCEKEY%
echo Asset: %ASSET%
echo Timeframe: %TIMEFRAME%
echo Duration: %DURATION%
echo Lookback: %LOOKBACK%
echo Strategy version reset: %STRATEGYVERSION%
echo Payout: %PAYOUT%
echo.
set /p "CONFIRM=Type RUN to start this local research workflow: "
if /I not "%CONFIRM%"=="RUN" goto cancel

echo.
echo Step 1/8 - Convert raw CSV dry-run...
cd /d "%~dp0bot"
python tools\convert_to_replay_candles.py "external_inputs\%RAWCSV%" --asset "%ASSET%" --timeframe %TIMEFRAME% --source-key "%SOURCEKEY%" --output "external_inputs\%REPLAYCSV%"
if errorlevel 1 goto error

echo.
echo Step 2/8 - Convert raw CSV write...
python tools\convert_to_replay_candles.py "external_inputs\%RAWCSV%" --asset "%ASSET%" --timeframe %TIMEFRAME% --source-key "%SOURCEKEY%" --output "external_inputs\%REPLAYCSV%" --yes
if errorlevel 1 goto error

echo.
echo Step 3/8 - Inventory check...
python tools\replay_csv_inventory.py
if errorlevel 1 goto error

echo.
echo Step 4/8 - Import candles dry-run...
python tools\import_replay_candles.py "external_inputs\%REPLAYCSV%"
if errorlevel 1 goto error

echo.
echo Step 5/8 - Import candles write...
python tools\import_replay_candles.py "external_inputs\%REPLAYCSV%" --yes
if errorlevel 1 goto error

echo.
echo Step 6/8 - Reset old research signals/outcomes for same source and strategy version...
python tools\replay_reset_research_for_source.py --source-key "%SOURCEKEY%" --strategy-version "%STRATEGYVERSION%" --asset "%ASSET%"
if errorlevel 1 goto error
python tools\replay_reset_research_for_source.py --source-key "%SOURCEKEY%" --strategy-version "%STRATEGYVERSION%" --asset "%ASSET%" --yes
if errorlevel 1 goto error

echo.
echo Step 7/8 - Run replay signals dry-run...
python tools\run_replay_signals.py --source-key "%SOURCEKEY%" --asset "%ASSET%" --timeframe %TIMEFRAME% --duration %DURATION% --analysis-lookback %LOOKBACK% --progress-every 5000
if errorlevel 1 goto error

echo.
echo Step 7/8 - Run replay signals write...
python tools\run_replay_signals.py --source-key "%SOURCEKEY%" --asset "%ASSET%" --timeframe %TIMEFRAME% --duration %DURATION% --analysis-lookback %LOOKBACK% --progress-every 5000 --yes
if errorlevel 1 goto error

echo.
echo Step 8/8 - Evaluate outcomes dry-run...
python tools\evaluate_replay_outcomes.py --source-key "%SOURCEKEY%" --asset "%ASSET%" --payout %PAYOUT%
if errorlevel 1 goto error

echo.
echo Step 8/8 - Evaluate outcomes write...
python tools\evaluate_replay_outcomes.py --source-key "%SOURCEKEY%" --asset "%ASSET%" --payout %PAYOUT% --yes
if errorlevel 1 goto error

echo.
echo Final report - multi-source stability...
python tools\replay_multi_source_report.py
if errorlevel 1 goto error

echo.
echo Final report - counterfactual same strategy/asset...
python tools\replay_counterfactual_report.py --strategy-version "%STRATEGYVERSION%" --asset "%ASSET%" --payout %PAYOUT% --min-trades 100 --top 12
if errorlevel 1 goto error

echo.
echo Workflow finished successfully.
echo Copy the final report output and send it.
pause
exit /b 0

:missing_raw
echo Missing raw CSV filename. Cancelled.
pause
exit /b 1

:missing_asset
echo Missing asset. Cancelled.
pause
exit /b 1

:missing_source
echo Missing source key. Cancelled.
pause
exit /b 1

:cancel
echo Cancelled. No workflow was run.
pause
exit /b 0

:error
echo.
echo Workflow failed. Copy the output above and send it.
pause
exit /b 1
