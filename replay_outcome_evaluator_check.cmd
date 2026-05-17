@echo off
setlocal
cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB replay outcome evaluator smoke check
echo ============================================================
echo.
python tools\replay_outcome_evaluator_check.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Replay outcome evaluator check failed. Copy the output above and send it.
echo.
pause
exit /b 1
