Write-Host "Starting Subtitle Studio mockup..." -ForegroundColor Green
Write-Host ""

Set-Location $PSScriptRoot

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
}

& python .\mock_subtitle_studio.py
