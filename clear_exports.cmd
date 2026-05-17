@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB clear local CSV exports
echo ============================================================
echo.
echo This deletes only local CSV files under bot\exports.
echo It does not delete data.db and does not touch GitHub.
echo.

python tools\clear_exports.py
echo.
set /p CONFIRM=Type DELETE to remove local CSV exports: 
if /i not "%CONFIRM%"=="DELETE" goto cancelled

python tools\clear_exports.py --yes
if errorlevel 1 goto error

echo.
echo Running data quality report after cleanup...
python tools\data_quality_report.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:cancelled
echo.
echo Cancelled. No export files were deleted.
echo.
pause
exit /b 0

:error
echo.
echo Export cleanup failed. Copy the output above and send it for review.
echo.
pause
exit /b 1
