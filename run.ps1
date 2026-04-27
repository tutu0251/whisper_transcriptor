param(
    [string]$VenvDir = ""
)

Write-Host "Starting Whisper Transcriptor..." -ForegroundColor Green
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

$venvConfig = Join-Path $PSScriptRoot ".venv_path"
if (-not [string]::IsNullOrWhiteSpace($VenvDir)) {
    Set-Content -Path $venvConfig -Value $VenvDir -Encoding ascii
} elseif (Test-Path $venvConfig) {
    $VenvDir = (Get-Content -Path $venvConfig -TotalCount 1).Trim()
}
if ([string]::IsNullOrWhiteSpace($VenvDir)) {
    $VenvDir = ".venv"
    Set-Content -Path $venvConfig -Value $VenvDir -Encoding ascii
}

$activateScript = Join-Path $PSScriptRoot "$VenvDir\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
} else {
    Write-Host "[WARN] Virtual environment not found: '$VenvDir'" -ForegroundColor Yellow
    Write-Host "[WARN] Using system Python." -ForegroundColor Yellow
}

# Run the application
& python main.py
$exitCode = $LASTEXITCODE

# Keep window open
Read-Host "Press Enter to exit"
exit $exitCode