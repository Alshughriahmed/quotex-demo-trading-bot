@echo off
cd /d "%~dp0bot"
echo.
echo QTB replay counterfactual report
echo.
set /p STRATEGY=Strategy version filter, empty for ALL, example replay_signal_only_v1_lookback_300: 
set /p ASSET=Asset filter, empty for ALL, example USD/CAD: 
set /p PAYOUT=Theoretical payout, empty for 0.80: 
if "%PAYOUT%"=="" set PAYOUT=0.80
set /p MINTRADES=Minimum trades per bucket, empty for 100: 
if "%MINTRADES%"=="" set MINTRADES=100
set /p TOPN=Top rows per section, empty for 12: 
if "%TOPN%"=="" set TOPN=12

echo.
if "%STRATEGY%"=="" goto no_strategy
if "%ASSET%"=="" goto strategy_only
python tools\replay_counterfactual_report.py --strategy-version "%STRATEGY%" --asset "%ASSET%" --payout %PAYOUT% --min-trades %MINTRADES% --top %TOPN%
goto done

:strategy_only
python tools\replay_counterfactual_report.py --strategy-version "%STRATEGY%" --payout %PAYOUT% --min-trades %MINTRADES% --top %TOPN%
goto done

:no_strategy
if "%ASSET%"=="" goto no_filters
python tools\replay_counterfactual_report.py --asset "%ASSET%" --payout %PAYOUT% --min-trades %MINTRADES% --top %TOPN%
goto done

:no_filters
python tools\replay_counterfactual_report.py --payout %PAYOUT% --min-trades %MINTRADES% --top %TOPN%

goto done

:done
echo.
echo Replay counterfactual report finished.
pause
