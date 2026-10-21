@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo   ARGUS TECHNOLOGIES - DESKTOP EXECUTABLE & INSTALLER BUILDER
echo ================================================================
echo.

cd /d "%~dp0"

echo [1/6] Checking Python environment...
python --version
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo.
echo [2/6] Ensuring build tools are installed (pywebview, waitress, pyinstaller)...
pip install pywebview waitress pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
)

echo.
echo [3/6] Cleaning previous build artifacts...
if exist "build" rd /s /q "build"
if exist "dist\ArgusAttendance.exe" del /f /q "dist\ArgusAttendance.exe"
if exist "dist\ArgusAttendance_Setup_v2.0.exe" del /f /q "dist\ArgusAttendance_Setup_v2.0.exe"

echo.
echo [4/6] Building standalone single-file Windows executable (.exe)...
echo Packaging Python runtime, Waitress WSGI, OpenCV, PyWebView, and all assets...
pyinstaller --noconfirm ArgusAttendance.spec

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed! Please review the error log above.
    pause
    exit /b 1
)

echo.
echo [5/6] Building Windows Setup Installer (Inno Setup)...
set "ISCC_PATH="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH (
    for /f "delims=" %%I in ('where iscc 2^>nul') do set "ISCC_PATH=%%I"
)

if defined ISCC_PATH (
    echo Compiling Setup Program using: "!ISCC_PATH!"...
    "!ISCC_PATH!" "%~dp0installer.iss"
    if errorlevel 1 (
        echo [WARNING] Installer compilation failed, but standalone .exe was built successfully.
    ) else (
        echo [OK] Installer created successfully!
    )
) else (
    echo [INFO] Inno Setup compiler (ISCC.exe) not found. Skipping setup installer compilation.
)

echo.
echo [6/6] Cleaning intermediate build files and updating launcher shortcuts...
if exist "build" rd /s /q "build"

REM Update root launcher shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%~dp0ArgusAttendance.lnk'); $s.TargetPath = '%~dp0dist\ArgusAttendance.exe'; $s.WorkingDirectory = '%~dp0dist'; if (Test-Path '%~dp0static\favicon.ico') { $s.IconLocation = '%~dp0static\favicon.ico' }; $s.Description = 'Argus Attendance Desktop Application'; $s.Save()" 2>nul

echo.
echo ================================================================
echo [SUCCESS] Build Process Completed!
echo.
echo 1. WINDOWS SETUP INSTALLER (Recommended for Clients):
echo    dist\ArgusAttendance_Setup_v2.0.exe
echo.
echo 2. PORTABLE STANDALONE EXECUTABLE:
echo    dist\ArgusAttendance.exe
echo.
echo SHARING WITH CLIENTS:
echo Send "dist\ArgusAttendance_Setup_v2.0.exe" to your clients.
echo When they run it, it installs like any standard Windows software:
echo - Creates Start Menu and Desktop shortcuts with Argus icon
echo - Adds an uninstaller in Windows Settings / Control Panel
echo - Installs cleanly into Program Files / LocalAppData
echo ================================================================
echo.
pause
