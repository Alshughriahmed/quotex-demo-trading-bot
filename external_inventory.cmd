@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB external dataset inventory
echo ============================================================
echo.
echo This lists external files and archive names only.
echo It does not extract archives and does not print file contents.
echo.

python tools\external_inventory.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo External inventory failed. Copy the output above and send it for review.
echo.
pause
exit /b 1
