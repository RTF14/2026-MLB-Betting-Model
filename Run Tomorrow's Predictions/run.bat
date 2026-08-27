@echo off
setlocal
cd /d "%~dp0"
python run_tomorrow_predictions.py %*
endlocal
