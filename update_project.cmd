@echo off
setlocal

cd /d "%~dp0"

echo.
echo ============================================================
echo  QTB local updater
echo ============================================================
echo.

echo [1/4] Pulling latest changes from GitHub...
git pull origin main
if errorlevel 1 goto error

echo.
echo [2/4] Recent commits:
git log -4 --oneline
if errorlevel 1 goto error

echo.
echo [3/4] Running Python syntax checks for the full bot folder...
python -m compileall -q bot
if errorlevel 1 goto error

echo.
echo [4/4] Checking local Git status...
git status --short
if errorlevel 1 goto error

echo.
echo ============================================================
echo  Update finished successfully.
echo  If no files are listed under Git status, the folder is clean.
echo ============================================================
echo.
pause
exit /b 0

:error
echo.
echo ============================================================
echo  Update failed. Copy the output above and send it for review.
echo ============================================================
echo.
pause
exit /b 1
