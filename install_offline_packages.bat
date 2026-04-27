@echo off
setlocal EnableDelayedExpansion

set "USE_CUDA=0"
set "INCLUDE_TORCHAUDIO=0"
set "INCLUDE_TORCHVISION=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--cuda" (
    set "USE_CUDA=1"
    shift
    goto parse_args
)
if /I "%~1"=="--torchaudio" (
    set "INCLUDE_TORCHAUDIO=1"
    shift
    goto parse_args
)
if /I "%~1"=="--torchvision" (
    set "INCLUDE_TORCHVISION=1"
    shift
    goto parse_args
)
echo Unknown argument: %~1
exit /b 1

:args_done
echo Installing offline Python packages...
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

for /f %%i in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set "PY_VER=%%i"
if not "%PY_VER%"=="3.10" (
    echo Warning: this wheelhouse appears to target Python 3.10, but the active interpreter is Python %PY_VER%.
)

if not exist "offline_packages" (
    echo offline_packages folder not found.
    exit /b 1
)

echo Installing pinned packaging tools from offline cache...
python -m pip install --no-index --find-links offline_packages --prefer-binary --upgrade pip==26.0.1 setuptools==81.0.0
if errorlevel 1 exit /b %errorlevel%

if "%USE_CUDA%"=="1" (
    echo Installing optional CUDA PyTorch packages from offline cache...
    set "CUDA_PACKAGES=torch==2.7.1+cu118"
    if "%INCLUDE_TORCHAUDIO%"=="1" set "CUDA_PACKAGES=!CUDA_PACKAGES! torchaudio==2.7.1+cu118"
    if "%INCLUDE_TORCHVISION%"=="1" set "CUDA_PACKAGES=!CUDA_PACKAGES! torchvision==0.22.1+cu118"
    python -m pip install --no-index --find-links offline_packages --prefer-binary --upgrade !CUDA_PACKAGES!
    if errorlevel 1 exit /b %errorlevel%

    set "TEMP_REQUIREMENTS=%TEMP%\requirements.offline.no_torch.txt"
    powershell -NoProfile -Command "(Get-Content 'requirements.txt') | Where-Object { $_ -notmatch '^\s*torch(\b|[<>=])' } | Set-Content '!TEMP_REQUIREMENTS!'"
    if errorlevel 1 exit /b %errorlevel%

    echo Installing non-torch project requirements from offline cache...
    python -m pip install --no-index --find-links offline_packages --prefer-binary --upgrade -r "!TEMP_REQUIREMENTS!"
    if errorlevel 1 exit /b %errorlevel%
) else (
    echo Installing project requirements from offline cache...
    python -m pip install --no-index --find-links offline_packages --prefer-binary --upgrade -r requirements.txt
    if errorlevel 1 exit /b %errorlevel%
)

echo.
echo Offline package installation completed.
