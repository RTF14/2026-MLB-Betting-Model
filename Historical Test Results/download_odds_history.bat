@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0download_odds_history.ps1"
