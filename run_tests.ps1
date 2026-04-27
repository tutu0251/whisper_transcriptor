param(
    [string]$VenvDir = "",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$TestArgs
)

Write-Host "Running unit tests..." -ForegroundColor Green
Write-Host ""

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

$env:PYTHONPATH = $PSScriptRoot
$env:QT_QPA_PLATFORM = "offscreen"

if (-not $TestArgs -or $TestArgs.Count -eq 0) {
    & python -m unittest discover -s tests -p "test_*.py"
} else {
    & python -m unittest @TestArgs
}

$exitCode = $LASTEXITCODE
Write-Host ""
Read-Host "Press Enter to exit"
exit $exitCode
