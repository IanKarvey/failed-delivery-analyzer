@echo off
rem Starts the text-menu (console) version of the Delivery Analyzer. Installs matplotlib and pillow first if missing.
cd /d "%~dp0"

set PY=python
%PY% --version >nul 2>&1
if errorlevel 1 set PY=py
%PY% --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Download it from https://www.python.org/downloads/
    echo During setup, tick "Add python.exe to PATH".
    pause
    exit /b 1
)

%PY% -c "import matplotlib, PIL" >nul 2>&1
if errorlevel 1 (
    echo Installing required libraries ^(matplotlib, pillow^)... this needs internet, once only.
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Install failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

%PY% main.py --console
pause
