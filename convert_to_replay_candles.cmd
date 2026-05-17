@echo off
cd /d "%~dp0bot"
echo.
echo QTB candle CSV converter
echo.
set /p ASSET=Asset, example EUR/USD: 
set /p TIMEFRAME=Timeframe seconds, example 60: 
if "%TIMEFRAME%"=="" set TIMEFRAME=60
set /p SOURCEKEY=Source key, example dukascopy_csv: 
if "%SOURCEKEY%"=="" set SOURCEKEY=converted_csv
echo.
echo Dry run...
python tools\convert_to_replay_candles.py --asset "%ASSET%" --timeframe %TIMEFRAME% --source-key "%SOURCEKEY%"
if errorlevel 1 goto error
echo.
set /p CONFIRM=Type CONVERT to write replay-ready CSV: 
if /I not "%CONFIRM%"=="CONVERT" goto cancel
python tools\convert_to_replay_candles.py --asset "%ASSET%" --timeframe %TIMEFRAME% --source-key "%SOURCEKEY%" --yes
if errorlevel 1 goto error
echo.
echo Done. Now run replay_csv_inventory.
pause
exit /b 0

:cancel
echo Cancelled. No output file was written.
pause
exit /b 0

:error
echo Converter failed. Copy the output above and send it.
pause
exit /b 1
