@echo off
cd /d "%~dp0bot"
python tools\replay_pipeline_check.py
pause
