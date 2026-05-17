@echo off
cd /d "%~dp0bot"
python tools\external_dataset_drilldown.py
pause
