@echo off
setlocal

echo Running unit tests...
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

set "PYTHONPATH=%CD%"
set "QT_QPA_PLATFORM=offscreen"

if "%~1"=="" (
    python -m unittest discover -s tests -p "test_*.py"
) else (
    python -m unittest %*
)

set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%
