param(
    [string]$Date = "",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($Date)) {
    & $PythonExe "$Here\run_tomorrow_predictions.py"
} else {
    & $PythonExe "$Here\run_tomorrow_predictions.py" --date $Date
}
