@echo off
title Launching Argus Attendance Intelligence v2.0.0...
cd /d "%~dp0"
if exist "dist\Argus-Attendance-Intelligence.exe" (
    start "" "%~dp0dist\Argus-Attendance-Intelligence.exe"
) else if exist "dist\ArgusAttendance.exe" (
    start "" "%~dp0dist\ArgusAttendance.exe"
) else if exist "dist\ArgusAttendance\ArgusAttendance.exe" (
    start "" "%~dp0dist\ArgusAttendance\ArgusAttendance.exe"
) else (
    echo [ERROR] Could not find executable in dist\.
    echo Please run build_desktop_exe.bat first to build the application.
    pause
)
