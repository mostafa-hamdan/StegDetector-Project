@echo off
REM StegDetector Setup Script
REM This script sets up the virtual environment and installs all dependencies

setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
cd /d "%~dp0"

echo.
echo ========================================
echo StegDetector - Initial Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo ========================================
    echo ERROR: Python is not installed or not in PATH
    echo ========================================
    echo.
    echo Please install Python 3.10 or higher from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo Python found!
python --version
echo.

REM Check if ffmpeg is installed
ffmpeg -version >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo ========================================
    echo WARNING: ffmpeg is not found in PATH
    echo ========================================
    echo.
    echo ffmpeg is required for video processing.
    echo.
    echo Please install ffmpeg from:
    echo   https://ffmpeg.org/download.html
    echo.
    echo Then add its bin directory to your PATH.
    echo.
    echo For Windows:
    echo   1. Download FFmpeg build
    echo   2. Extract to a folder (e.g., C:\ffmpeg)
    echo   3. Add C:\ffmpeg\bin to Windows PATH
    echo.
    echo Continue setup? (Y/N)
    set /p continue=
    if /i not "!continue!"=="Y" (
        exit /b 1
    )
)

REM Check if venv already exists
if exist "venv" (
    echo Virtual environment already exists.
    echo.
    echo Do you want to reinstall? (Y/N)
    set /p reinstall=
    if /i "!reinstall!"=="Y" (
        echo Removing old virtual environment...
        rmdir /s /q venv
        if !errorlevel! neq 0 (
            echo Failed to remove venv. Please delete manually and try again.
            pause
            exit /b 1
        )
    ) else (
        echo Skipping virtual environment creation.
        goto skip_venv
    )
)

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv venv

if !errorlevel! neq 0 (
    echo.
    echo ========================================
    echo ERROR: Failed to create virtual environment
    echo ========================================
    echo.
    pause
    exit /b 1
)

echo Virtual environment created successfully!
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

if !errorlevel! neq 0 (
    echo.
    echo ========================================
    echo ERROR: Failed to activate virtual environment
    echo ========================================
    echo.
    pause
    exit /b 1
)

echo Virtual environment activated!
echo.

:skip_venv

REM Activate virtual environment (in case it already existed)
call venv\Scripts\activate.bat

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

if !errorlevel! neq 0 (
    echo.
    echo ========================================
    echo WARNING: Failed to upgrade pip
    echo ========================================
    echo.
    echo Continuing anyway...
    echo.
)

REM Install requirements
echo.
echo Installing dependencies from requirements.txt...
echo.
pip install -r requirements.txt

if !errorlevel! neq 0 (
    echo.
    echo ========================================
    echo ERROR: Failed to install dependencies
    echo ========================================
    echo.
    echo Please check the error messages above.
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo Next steps:
echo 1. Double-click 'run_stegdetector.bat' to start the app
echo.
echo Or from command line:
echo   run_stegdetector.bat
echo.
echo The app will open at: http://localhost:8501
echo.
pause
