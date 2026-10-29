@echo off
rem Delivery Analyzer (terminal version) launcher - installs matplotlib if missing, then starts the menu.
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

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo This program needs Python 3.9 or newer. Download the latest from https://www.python.org/downloads/
    pause
    exit /b 1
)

%PY% -c "import matplotlib" >nul 2>&1
if errorlevel 1 (
    echo Installing the required library ^(matplotlib^)... this needs internet, once only.
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Install failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

%PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo Note: this Python was installed without Tk, so the charts ^(menu option 11^) cannot open.
    echo To fix it, run the Python installer again, choose Modify, and tick "tcl/tk and IDLE".
    echo.
)

%PY% main.py
if errorlevel 1 pause
