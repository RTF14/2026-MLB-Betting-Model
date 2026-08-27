param(
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

& $PythonExe "$Here\run_historical_tests.py"
