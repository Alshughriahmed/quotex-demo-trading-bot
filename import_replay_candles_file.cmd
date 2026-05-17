@echo off
cd /d "%~dp0bot"
echo.
echo QTB explicit replay candle CSV importer
echo.
echo This imports one selected replay-ready CSV into research_market_candles only.
echo It does not start the bot, does not connect to a broker, and does not trade.
echo It does not modify native trades or print secrets.
echo.
set /p INPUTCSV=Replay-ready CSV filename in external_inputs, example replay_ready_DAT_ASCII_USDCAD_M1_202603.csv: 
if "%INPUTCSV%"=="" goto missing_input

echo.
echo Dry run...
python tools\import_replay_candles.py "external_inputs\%INPUTCSV%"
if errorlevel 1 goto error
echo.
set /p CONFIRM=Type IMPORT to import this CSV into research_market_candles: 
if /I not "%CONFIRM%"=="IMPORT" goto cancel
python tools\import_replay_candles.py "external_inputs\%INPUTCSV%" --yes
if errorlevel 1 goto error
echo.
echo Done. Now run replay_csv_inventory or run_replay_research_workflow.
pause
exit /b 0

:missing_input
echo Missing replay-ready CSV filename. Cancelled.
pause
exit /b 1

:cancel
echo Import cancelled. No candles were imported.
pause
exit /b 0

:error
echo Replay candle import failed. Copy the output above and send it.
pause
exit /b 1
