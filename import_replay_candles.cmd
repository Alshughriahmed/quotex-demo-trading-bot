@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB replay candle CSV importer
echo ============================================================
echo.
echo This imports historical candles into research_market_candles only.
echo It does not start the bot, does not connect to a broker, and does not trade.
echo.
echo Put a candle CSV file in bot\external_inputs first.
echo Required columns:
echo asset,timeframe_seconds,candle_time,open,high,low,close
echo Optional columns:
echo source_key,volume,is_closed
echo.

python tools\import_replay_candles.py
if errorlevel 1 goto error

echo.
set /p CONFIRM=Type IMPORT to import the CSV candles into research_market_candles: 
if /I not "%CONFIRM%"=="IMPORT" goto cancel

python tools\import_replay_candles.py --yes
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:cancel
echo.
echo Import cancelled. No candles were imported.
echo.
pause
exit /b 0

:error
echo.
echo Replay candle import failed. Copy the output above and send it.
echo.
pause
exit /b 1
