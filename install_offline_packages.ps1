param(
    [switch]$Cuda,
    [switch]$IncludeTorchAudio,
    [switch]$IncludeTorchVision
)

$ErrorActionPreference = "Stop"

Write-Host "Installing offline Python packages..." -ForegroundColor Green
Write-Host ""

Set-Location $PSScriptRoot

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
}

$pythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($pythonVersion -ne "3.10") {
    Write-Warning "This wheelhouse appears to target Python 3.10, but the active interpreter is Python $pythonVersion."
}

$wheelhouse = Join-Path $PSScriptRoot "offline_packages"
if (-not (Test-Path $wheelhouse)) {
    throw "offline_packages folder not found: $wheelhouse"
}

$commonArgs = @(
    "-m", "pip", "install",
    "--no-index",
    "--find-links", $wheelhouse,
    "--prefer-binary"
)

Write-Host "Installing pinned packaging tools from offline cache..." -ForegroundColor Cyan
& python @commonArgs "--upgrade" "pip==26.0.1" "setuptools==81.0.0"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Cuda) {
    $extraPackages = @("torch==2.7.1+cu118")

    if ($IncludeTorchAudio) {
        $extraPackages += "torchaudio==2.7.1+cu118"
    }

    if ($IncludeTorchVision) {
        $extraPackages += "torchvision==0.22.1+cu118"
    }

    Write-Host "Installing optional PyTorch variants from offline cache..." -ForegroundColor Cyan
    & python @commonArgs "--upgrade" @extraPackages
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($Cuda) {
    $tempRequirements = Join-Path $env:TEMP "requirements.offline.no_torch.txt"
    Get-Content "requirements.txt" | Where-Object {
        $_ -notmatch '^\s*torch(\b|[<>=])'
    } | Set-Content $tempRequirements

    Write-Host "Installing non-torch project requirements from offline cache..." -ForegroundColor Cyan
    & python @commonArgs "--upgrade" "-r" $tempRequirements
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "Installing project requirements from offline cache..." -ForegroundColor Cyan
    & python @commonArgs "--upgrade" "-r" "requirements.txt"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "Offline package installation completed." -ForegroundColor Green
