@echo off
echo Starting Subtitle Studio mockup...
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

python mock_subtitle_studio.py
