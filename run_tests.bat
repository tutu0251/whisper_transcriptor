@echo off
setlocal

echo Running unit tests...
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

set "PYTHONPATH=%CD%"
set "QT_QPA_PLATFORM=offscreen"

if not "%~1"=="" shift

if "%~1"=="" (
    python -m unittest discover -s tests -p "test_*.py"
) else (
    python -m unittest %*
)

set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%
