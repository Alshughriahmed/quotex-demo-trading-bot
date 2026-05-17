@echo off
cd /d "%~dp0bot"
python tools\replay_csv_inventory.py
pause
