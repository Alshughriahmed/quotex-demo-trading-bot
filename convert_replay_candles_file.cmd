@echo off
cd /d "%~dp0bot"
echo.
echo QTB explicit candle CSV converter
echo.
echo This converts one selected CSV file into QTB replay CSV format.
echo It does not import data, does not start the bot, and does not trade.
echo.
set /p INPUTCSV=Input CSV filename in external_inputs, example DAT_ASCII_USDCAD_M1_202603.csv: 
if "%INPUTCSV%"=="" goto missing_input
set /p ASSET=Asset, example USD/CAD: 
if "%ASSET%"=="" goto missing_asset
set /p TIMEFRAME=Timeframe seconds, example 60: 
if "%TIMEFRAME%"=="" set TIMEFRAME=60
set /p SOURCEKEY=Source key, example histdata_usdcad_m1_202603: 
if "%SOURCEKEY%"=="" goto missing_source

echo.
echo Dry run...
python tools\convert_to_replay_candles.py "%INPUTCSV%" --asset "%ASSET%" --timeframe %TIMEFRAME% --source-key "%SOURCEKEY%"
if errorlevel 1 goto error
echo.
set /p CONFIRM=Type CONVERT to write replay-ready CSV: 
if /I not "%CONFIRM%"=="CONVERT" goto cancel
python tools\convert_to_replay_candles.py "%INPUTCSV%" --asset "%ASSET%" --timeframe %TIMEFRAME% --source-key "%SOURCEKEY%" --yes
if errorlevel 1 goto error
echo.
echo Done. Now run replay_csv_inventory.
pause
exit /b 0

:missing_input
echo Missing input CSV filename. Cancelled.
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
echo Cancelled. No output file was written.
pause
exit /b 0

:error
echo Converter failed. Copy the output above and send it.
pause
exit /b 1
