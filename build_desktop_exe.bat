@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo   ARGUS TECHNOLOGIES - STANDALONE DESKTOP EXECUTABLE BUILDER
echo ================================================================
echo.

cd /d "%~dp0"

echo [1/5] Checking Python environment...
python --version
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo.
echo [2/5] Ensuring build tools are installed (pywebview, waitress, pyinstaller)...
pip install pywebview waitress pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
)

echo.
echo [3/5] Cleaning previous build artifacts...
if exist "build" rd /s /q "build"
if exist "dist\ArgusAttendance.exe" del /f /q "dist\ArgusAttendance.exe"

echo.
echo [4/5] Building standalone single-file Windows executable (.exe)...
echo Packaging Python runtime, Waitress WSGI, OpenCV, PyWebView, and all assets...
pyinstaller --noconfirm ArgusAttendance.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Please review the error log above.
    pause
    exit /b 1
)

echo.
echo [5/5] Cleaning intermediate build files and updating launcher shortcuts...
if exist "build" rd /s /q "build"

REM Update root launcher shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%~dp0ArgusAttendance.lnk'); $s.TargetPath = '%~dp0dist\ArgusAttendance.exe'; $s.WorkingDirectory = '%~dp0dist'; if (Test-Path '%~dp0static\favicon.ico') { $s.IconLocation = '%~dp0static\favicon.ico' }; $s.Description = 'Argus Attendance Desktop Application'; $s.Save()" 2>nul

echo.
echo ================================================================
echo [SUCCESS] Standalone Single-File Executable Ready!
echo.
echo Standalone Executable Location:
echo %~dp0dist\ArgusAttendance.exe
echo.
echo SHARING INSTRUCTIONS:
echo You can directly send "dist\ArgusAttendance.exe" to your clients
echo via WhatsApp, Google Drive, Pendrive, or Email.
echo It is a 100%% portable standalone file with NO external folder dependencies!
echo ================================================================
echo.
pause
