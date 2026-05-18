@echo off
setlocal EnableExtensions
cd /d "%~dp0bot"

echo.
echo QTB automated replay batch folder workflow
echo.
echo This runs locally over CSV files in bot\external_inputs.
echo It does not upload files, does not start the bot, does not connect to a broker, and does not trade.
echo.

set /p "SYMBOL=Symbol filter, empty for ALL, example USDCAD or EURUSD: "
set /p "MONTH=Month filter, empty for ALL, example 202601 or 2026-01: "
set /p "DURATION=Duration seconds, empty for 60: "
if "%DURATION%"=="" set "DURATION=60"
set /p "LOOKBACK=Analysis lookback candles, empty for 300: "
if "%LOOKBACK%"=="" set "LOOKBACK=300"
set /p "PAYOUT=Theoretical payout, empty for 0.80: "
if "%PAYOUT%"=="" set "PAYOUT=0.80"
set /p "LIMITFILES=Limit files, empty for ALL, example 1 for test: "
if "%LIMITFILES%"=="" set "LIMITFILES=0"

echo.
echo First run will be DRY-RUN only.
echo If it looks correct, run again and type WRITE.
echo.
set /p "MODE=Type WRITE to actually process/import/evaluate, or press Enter for DRY-RUN: "

echo.
if /I "%MODE%"=="WRITE" goto write_mode

python tools\replay_batch_folder_workflow.py --symbol "%SYMBOL%" --month "%MONTH%" --duration %DURATION% --analysis-lookback %LOOKBACK% --payout %PAYOUT% --limit-files %LIMITFILES%
goto done

:write_mode
python tools\replay_batch_folder_workflow.py --symbol "%SYMBOL%" --month "%MONTH%" --duration %DURATION% --analysis-lookback %LOOKBACK% --payout %PAYOUT% --limit-files %LIMITFILES% --yes

goto done

:done
echo.
echo Replay batch folder workflow finished.
pause
