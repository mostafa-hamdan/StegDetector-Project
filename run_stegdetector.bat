@echo off
REM StegDetector Startup Script
REM This script activates the virtual environment and starts the Streamlit app

setlocal enabledelayedexpansion

REM Get the directory where this batch file is located
cd /d "%~dp0"

REM Check if venv exists
if not exist "venv" (
    echo.
    echo ========================================
    echo ERROR: Virtual environment not found!
    echo ========================================
    echo.
    echo Please run the setup script first:
    echo   setup.bat
    echo.
    pause
    exit /b 1
)

REM Check if streamlit_app.py exists in StegDetector folder
if not exist "StegDetector\streamlit_app.py" (
    echo.
    echo ========================================
    echo ERROR: streamlit_app.py not found!
    echo ========================================
    echo.
    echo Make sure you're in the correct StegDetector directory.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if activation was successful
if !errorlevel! neq 0 (
    echo.
    echo ========================================
    echo ERROR: Failed to activate virtual environment
    echo ========================================
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo StegDetector - Starting Streamlit App
echo ========================================
echo.
echo Virtual environment activated successfully!
echo Starting Streamlit application...
echo.
echo The app will open in your browser at:
echo http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

REM Start Streamlit app
streamlit run StegDetector\streamlit_app.py

REM If streamlit closes, show a message
echo.
echo ========================================
echo Streamlit has stopped
echo ========================================
echo.
pause
