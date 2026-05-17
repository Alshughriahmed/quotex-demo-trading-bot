@echo off
cd /d "%~dp0bot"
echo.
echo QTB source-scoped replay signal runner
echo.
set /p SOURCEKEY=Source key, example histdata_usdcad_m1_202603: 
if "%SOURCEKEY%"=="" goto missing_source
set /p ASSET=Asset, example USD/CAD: 
if "%ASSET%"=="" goto missing_asset
set /p TIMEFRAME=Timeframe seconds, example 60: 
if "%TIMEFRAME%"=="" set TIMEFRAME=60
set /p DURATION=Duration seconds, example 60: 
if "%DURATION%"=="" set DURATION=60
set /p LOOKBACK=Analysis lookback candles, example 300, empty for 300: 
if "%LOOKBACK%"=="" set LOOKBACK=300

echo.
echo Dry run...
python tools\run_replay_signals.py --source-key "%SOURCEKEY%" --asset "%ASSET%" --timeframe %TIMEFRAME% --duration %DURATION% --analysis-lookback %LOOKBACK% --progress-every 5000
if errorlevel 1 goto error
echo.
set /p CONFIRM=Type SIGNALS to insert research signals for this source: 
if /I not "%CONFIRM%"=="SIGNALS" goto cancel
python tools\run_replay_signals.py --source-key "%SOURCEKEY%" --asset "%ASSET%" --timeframe %TIMEFRAME% --duration %DURATION% --analysis-lookback %LOOKBACK% --progress-every 5000 --yes
if errorlevel 1 goto error
echo.
echo Done.
pause
exit /b 0

:missing_source
echo Missing source key. Cancelled.
pause
exit /b 1

:missing_asset
echo Missing asset. Cancelled.
pause
exit /b 1

:cancel
echo Cancelled. No signals were inserted.
pause
exit /b 0

:error
echo Replay signal run failed. Copy the output above and send it.
pause
exit /b 1
