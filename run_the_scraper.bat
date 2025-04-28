@echo off
setlocal enabledelayedexpansion

:: Set the project root to the folder where this batch file is located

REM Set project directory to current folder
set "PROJECT_ROOT=%~dp0"

:: Move to project directory
cd /d "%PROJECT_ROOT%"

:: Check if Python is installed
REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Please install Python and try again.
    pause
    exit /b
)

REM Create virtual environment if it doesn't exist
:: Check if virtual environment folder exists
if not exist "venv" (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Failed to create virtual environment.
        exit /b 1
    )
) else (
    echo Virtual environment already exists.
)

:: Activate the virtual environment
call "%PROJECT_ROOT%venv\Scripts\activate.bat"

:: Install dependencies
if exist requirements.txt (
    echo 📦 Installing dependencies... from requirements.txt...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    echo Dependencies installed successfully.   

    if %errorlevel% neq 0 (
        echo Failed to install dependencies.
        pause
        exit /b
    ) 
) else (
    echo No requirements.txt found. Skipping dependency installation.
    echo You need to install dependencies manually.
    echo Please run: pip install -r requirements.txt
    echo Please Get the requirement.txt from the project repository.
    echo Exiting...
    )
REM Run GUI in hidden mode using pythonw.exe
echo 🪄 Launching GUI silently...
start "" "venv\Scripts\pythonssss.exe" gui.py
echo GUI launched successfully.
echo You can now close this batch window.

pause
REM Optional: kill this batch window immediately

exit