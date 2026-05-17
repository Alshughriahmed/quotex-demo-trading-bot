@echo off
setlocal

cd /d "%~dp0bot"

echo.
echo ============================================================
echo  QTB sanitized review package
echo ============================================================
echo.
echo This creates a safe zip for external AI/code review.
echo It excludes secrets, databases, logs, exports, external inputs, and archives.
echo.

python tools\make_review_package.py
if errorlevel 1 goto error

echo.
echo Done.
echo.
pause
exit /b 0

:error
echo.
echo Review package creation failed. Copy the output above and send it.
echo.
pause
exit /b 1
