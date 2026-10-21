@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo   ARGUS TECHNOLOGIES - DESKTOP EXECUTABLE BUILD SCRIPT
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
if exist "dist\ArgusAttendance" rd /s /q "dist\ArgusAttendance"

echo.
echo [4/5] Building standalone Windows executable with PyInstaller...
echo This may take 1-3 minutes to compile all models, templates, and libraries...
pyinstaller --noconfirm ArgusAttendance.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Please review the error log above.
    pause
    exit /b 1
)

echo.
echo [5/5] Cleaning intermediate build files and generating launch shortcuts...
REM Clean up intermediate build cache so user is not confused by incomplete files in build/
if exist "build" rd /s /q "build"

REM Create/Update root launcher batch file
(
echo @echo off
echo title Launching Argus Attendance Desktop App...
echo cd /d "%%~dp0"
echo if exist "dist\ArgusAttendance\ArgusAttendance.exe" ^(
echo     start "" "%%~dp0dist\ArgusAttendance\ArgusAttendance.exe"
echo ^) else ^(
echo     echo [ERROR] Could not find dist\ArgusAttendance\ArgusAttendance.exe.
echo     echo Please run build_desktop_exe.bat first to build the application.
echo     pause
echo ^)
) > "%~dp0Run_Argus_Attendance.bat"

REM Create/Update Windows shortcut (.lnk) in root
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%~dp0ArgusAttendance.lnk'); $s.TargetPath = '%~dp0dist\ArgusAttendance\ArgusAttendance.exe'; $s.WorkingDirectory = '%~dp0dist\ArgusAttendance'; if (Test-Path '%~dp0static\favicon.ico') { $s.IconLocation = '%~dp0static\favicon.ico' }; $s.Description = 'Argus Attendance Desktop Application'; $s.Save()" 2>nul

echo.
echo ================================================================
echo [SUCCESS] Build Completed Successfully!
echo.
echo YOU CAN LAUNCH THE APPLICATION VIA:
echo 1. Double click: ArgusAttendance.lnk (in this project root)
echo 2. Or double click: Run_Argus_Attendance.bat (in this project root)
echo 3. Or direct executable: dist\ArgusAttendance\ArgusAttendance.exe
echo.
echo NOTE: Do NOT run files inside temporary build folders.
echo The complete application is located in the "dist" directory.
echo ================================================================
echo.
pause
