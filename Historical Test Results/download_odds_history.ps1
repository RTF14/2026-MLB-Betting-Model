param(
    [string]$OutFile = "..\data\raw\mlb_odds_dataset.json"
)

$ErrorActionPreference = "Stop"
$url = "https://github.com/ArnavSaraogi/mlb-odds-scraper/releases/download/dataset/mlb_odds_dataset.json"
$resolved = Join-Path $PSScriptRoot $OutFile
$parent = Split-Path -Parent $resolved

New-Item -ItemType Directory -Force -Path $parent | Out-Null
Invoke-WebRequest -Uri $url -OutFile $resolved
Write-Host "Downloaded historical odds dataset to $resolved"
