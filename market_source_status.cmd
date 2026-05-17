@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB market source status
echo ============================================================
echo.
echo This checks the market-source adapter state.
echo It does not inspect or print account secrets.
echo.

python tools\market_source_status.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Market source status check failed. Copy the output above and send it.
echo.
pause
exit /b 1
