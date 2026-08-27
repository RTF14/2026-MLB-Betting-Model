@echo off
setlocal
cd /d "%~dp0"
python run_historical_tests.py %*
endlocal
