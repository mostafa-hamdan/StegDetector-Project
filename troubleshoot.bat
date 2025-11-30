@echo off
REM StegDetector Troubleshooting & Diagnostics Script

setlocal enabledelayedexpansion

cd /d "%~dp0"

:menu
cls
echo.
echo ========================================
echo StegDetector - Diagnostics & Troubleshooting
echo ========================================
echo.
echo What would you like to do?
echo.
echo 1. Check Python installation
echo 2. Check ffmpeg installation
echo 3. Check virtual environment
echo 4. Test dependencies
echo 5. Reinstall dependencies
echo 6. Reset virtual environment
echo 7. View application logs
echo 8. Exit
echo.
set /p choice=Enter your choice (1-8): 

if "%choice%"=="1" goto check_python
if "%choice%"=="2" goto check_ffmpeg
if "%choice%"=="3" goto check_venv
if "%choice%"=="4" goto test_deps
if "%choice%"=="5" goto reinstall_deps
if "%choice%"=="6" goto reset_venv
if "%choice%"=="7" goto view_logs
if "%choice%"=="8" goto exit
goto menu

:check_python
echo.
echo ========================================
echo Checking Python Installation
echo ========================================
echo.
python --version
if !errorlevel! equ 0 (
    echo.
    echo [OK] Python is installed and accessible
    echo.
    echo Python executable location:
    where python
) else (
    echo.
    echo [ERROR] Python is not found or not in PATH
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo Remember to check "Add Python to PATH"
)
echo.
pause
goto menu

:check_ffmpeg
echo.
echo ========================================
echo Checking ffmpeg Installation
echo ========================================
echo.
ffmpeg -version >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] ffmpeg is installed
    echo.
    ffmpeg -version | findstr version
    echo.
    echo ffmpeg location:
    where ffmpeg
) else (
    echo [ERROR] ffmpeg is not found or not in PATH
    echo.
    echo Please install ffmpeg from: https://ffmpeg.org/download.html
    echo Add the bin directory to your Windows PATH
)
echo.
pause
goto menu

:check_venv
echo.
echo ========================================
echo Checking Virtual Environment
echo ========================================
echo.
if exist "venv" (
    echo [OK] Virtual environment folder exists
    echo.
    echo Folder size and contents:
    dir venv /s | find "File(s)"
    echo.
    echo Checking if Python is in venv...
    if exist "venv\Scripts\python.exe" (
        echo [OK] Python executable found in venv
        venv\Scripts\python.exe --version
    ) else (
        echo [ERROR] Python executable not found in venv
        echo Try running: python -m venv venv
    )
) else (
    echo [ERROR] Virtual environment does not exist
    echo.
    echo Run setup.bat to create it:
    echo   setup.bat
)
echo.
pause
goto menu

:test_deps
echo.
echo ========================================
echo Testing Dependencies
echo ========================================
echo.
if not exist "venv" (
    echo [ERROR] Virtual environment not found
    echo Please run: setup.bat
    echo.
    pause
    goto menu
)

call venv\Scripts\activate.bat

echo Testing Python packages...
echo.

python -c "import numpy; print('[OK] NumPy installed')" 2>nul || echo [MISSING] NumPy
python -c "import scipy; print('[OK] SciPy installed')" 2>nul || echo [MISSING] SciPy
python -c "import sklearn; print('[OK] scikit-learn installed')" 2>nul || echo [MISSING] scikit-learn
python -c "import librosa; print('[OK] Librosa installed')" 2>nul || echo [MISSING] Librosa
python -c "import cv2; print('[OK] OpenCV installed')" 2>nul || echo [MISSING] OpenCV
python -c "import soundfile; print('[OK] Soundfile installed')" 2>nul || echo [MISSING] Soundfile
python -c "import imageio; print('[OK] imageio installed')" 2>nul || echo [MISSING] imageio
python -c "import streamlit; print('[OK] Streamlit installed')" 2>nul || echo [MISSING] Streamlit
python -c "import bcrypt; print('[OK] bcrypt installed')" 2>nul || echo [MISSING] bcrypt
python -c "import joblib; print('[OK] joblib installed')" 2>nul || echo [MISSING] joblib

echo.
echo Deactivating virtual environment...
deactivate

echo.
pause
goto menu

:reinstall_deps
echo.
echo ========================================
echo Reinstalling Dependencies
echo ========================================
echo.
if not exist "venv" (
    echo [ERROR] Virtual environment not found
    echo Please run: setup.bat
    echo.
    pause
    goto menu
)

call venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing packages from requirements.txt...
pip install -r requirements.txt

echo.
echo Deactivating virtual environment...
deactivate

echo.
echo Dependencies reinstalled!
pause
goto menu

:reset_venv
echo.
echo ========================================
echo Reset Virtual Environment
echo ========================================
echo.
echo This will DELETE the venv folder and create a new one.
echo All packages will be reinstalled.
echo.
set /p confirm=Are you sure? (Y/N): 
if /i not "%confirm%"=="Y" (
    goto menu
)

echo.
echo Removing old virtual environment...
if exist "venv" (
    rmdir /s /q venv
    if !errorlevel! equ 0 (
        echo [OK] Old venv removed
    ) else (
        echo [ERROR] Failed to remove venv
        echo Try closing all Python processes and try again
        pause
        goto menu
    )
)

echo.
echo Creating new virtual environment...
python -m venv venv

if !errorlevel! equ 0 (
    echo [OK] New venv created
) else (
    echo [ERROR] Failed to create venv
    pause
    goto menu
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing packages...
pip install -r requirements.txt

echo.
echo Deactivating...
deactivate

echo.
echo Virtual environment reset successfully!
pause
goto menu

:view_logs
echo.
echo ========================================
echo Application Logs Location
echo ========================================
echo.
echo Streamlit logs are typically found at:
echo   C:\Users\%USERNAME%\.streamlit\logs\
echo.
echo If you need to check what went wrong, look for:
echo   - streamlit_logger.log
echo.
echo You can also run the app and capture output:
echo   run_stegdetector.bat ^> app_output.txt 2^>^&1
echo.
pause
goto menu

:exit
echo.
echo Goodbye!
echo.
exit /b 0
