@echo off
cd /d "%~dp0bot"
python tools\replay_filter_validation_report.py
pause
