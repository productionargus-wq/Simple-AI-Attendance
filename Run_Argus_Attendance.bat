@echo off
title Launching Argus Attendance Desktop App...
cd /d "%~dp0"
if exist "dist\ArgusAttendance\ArgusAttendance.exe" (
    start "" "%~dp0dist\ArgusAttendance\ArgusAttendance.exe"
) else (
    echo [ERROR] Could not find dist\ArgusAttendance\ArgusAttendance.exe.
    echo Please run build_desktop_exe.bat first to build the application.
    pause
)
