@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB runtime diagnostics
echo ============================================================
echo.

python tools\diagnose_runtime.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Diagnostics failed. Copy the output above and send it for review.
echo.
pause
exit /b 1
