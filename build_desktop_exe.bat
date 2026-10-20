@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo   ARGUS TECHNOLOGIES - DESKTOP EXECUTABLE BUILD SCRIPT
echo ================================================================
echo.

cd /d "%~dp0"

echo [1/4] Checking Python environment...
python --version
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo.
echo [2/4] Ensuring build tools are installed (pywebview, waitress, pyinstaller)...
pip install pywebview waitress pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
)

echo.
echo [3/4] Cleaning previous build artifacts...
if exist "build" rd /s /q "build"
if exist "dist\ArgusAttendance" rd /s /q "dist\ArgusAttendance"

echo.
echo [4/4] Building standalone Windows executable with PyInstaller...
echo This may take 1-3 minutes to compile all models, templates, and libraries...
pyinstaller --noconfirm ArgusAttendance.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Please review the error log above.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo [SUCCESS] Build Completed Successfully!
echo.
echo Executable location:
echo %~dp0dist\ArgusAttendance\ArgusAttendance.exe
echo.
echo You can run this .exe on any Windows 10/11 machine.
echo It runs in its own native desktop window without opening any browser.
echo ================================================================
echo.
pause
