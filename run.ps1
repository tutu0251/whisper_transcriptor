Write-Host "Starting Whisper Transcriptor..." -ForegroundColor Green
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

# Activate virtual environment
& ".\.venv\Scripts\Activate.ps1"

# Run the application
& python main.py

# Keep window open
Read-Host "Press Enter to exit"