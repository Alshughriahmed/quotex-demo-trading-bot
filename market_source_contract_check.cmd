@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB market source contract check
echo ============================================================
echo.
echo This uses dummy candle data only.
echo It does not connect to a broker, does not start the bot, and does not trade.
echo.

python tools\market_source_contract_check.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Market source contract check failed. Copy the output above and send it.
echo.
pause
exit /b 1
