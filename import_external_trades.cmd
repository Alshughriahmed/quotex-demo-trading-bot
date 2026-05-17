@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB import external demo-bot trades
echo ============================================================
echo.
echo This imports trade rows into external_* tables only.
echo It does not touch native trades and does not print secrets.
echo.

python tools\import_external_trades.py
if errorlevel 1 goto error

echo.
set /p CONFIRM=Type IMPORT to import into external_* tables: 
if /i not "%CONFIRM%"=="IMPORT" goto cancelled

python tools\import_external_trades.py --yes
if errorlevel 1 goto error

echo.
echo Running data quality report after import...
python tools\data_quality_report.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:cancelled
echo.
echo Cancelled. No external records were imported.
echo.
pause
exit /b 0

:error
echo.
echo External import failed. Copy the output above and send it.
echo.
pause
exit /b 1
