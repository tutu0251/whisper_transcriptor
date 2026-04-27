@echo off
setlocal

echo Starting Whisper Transcriptor...
echo.

cd /d "%~dp0"

set "VENV_CONFIG=.venv_path"
set "VENV_DIR=%~1"
if not "%VENV_DIR%"=="" (
    > "%VENV_CONFIG%" echo %VENV_DIR%
) else (
    if exist "%VENV_CONFIG%" (
        set /p "VENV_DIR="<"%VENV_CONFIG%"
    )
)
if "%VENV_DIR%"=="" (
    set "VENV_DIR=.venv"
    > "%VENV_CONFIG%" echo %VENV_DIR%
)

if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
) else (
    echo [WARN] Virtual environment not found: "%VENV_DIR%"
    echo [WARN] Using system Python.
)

python main.py
set "EXIT_CODE=%ERRORLEVEL%"

pause
exit /b %EXIT_CODE%