param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$TestArgs
)

Write-Host "Running unit tests..." -ForegroundColor Green
Write-Host ""

Set-Location $PSScriptRoot

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
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
