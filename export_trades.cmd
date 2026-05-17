@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB local trade export
echo ============================================================
echo.

python tools\export_trades.py
if errorlevel 1 goto error

echo.
echo Export folder:
echo %cd%\exports
echo.
dir exports
echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Export failed. Copy the output above and send it for review.
echo.
pause
exit /b 1
