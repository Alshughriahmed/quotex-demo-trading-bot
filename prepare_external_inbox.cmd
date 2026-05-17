@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB prepare external dataset inbox
echo ============================================================
echo.
echo This creates local-only folders for future external demo-bot archives.
echo Archives and extracted files are ignored by Git.
echo.

python tools\prepare_external_inbox.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo External inbox preparation failed. Copy the output above and send it for review.
echo.
pause
exit /b 1
