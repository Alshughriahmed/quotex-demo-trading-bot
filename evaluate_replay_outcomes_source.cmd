@echo off
cd /d "%~dp0bot"
echo.
echo QTB source-scoped replay outcome evaluator
echo.
set /p SOURCEKEY=Source key, example histdata_usdcad_m1_202603: 
if "%SOURCEKEY%"=="" goto missing_source
set /p ASSET=Asset, example USD/CAD: 
if "%ASSET%"=="" goto missing_asset
set /p PAYOUT=Theoretical payout, example 0.80: 
if "%PAYOUT%"=="" set PAYOUT=0.80

echo.
echo Dry run...
python tools\evaluate_replay_outcomes.py --source-key "%SOURCEKEY%" --asset "%ASSET%" --payout %PAYOUT%
if errorlevel 1 goto error
echo.
set /p CONFIRM=Type OUTCOMES to insert research outcomes for this source: 
if /I not "%CONFIRM%"=="OUTCOMES" goto cancel
python tools\evaluate_replay_outcomes.py --source-key "%SOURCEKEY%" --asset "%ASSET%" --payout %PAYOUT% --yes
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
echo Cancelled. No outcomes were inserted.
pause
exit /b 0

:error
echo Replay outcome evaluation failed. Copy the output above and send it.
pause
exit /b 1
