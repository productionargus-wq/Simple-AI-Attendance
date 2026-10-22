# Argus AI Attendance - 1-Click Mobile App (APK) Build Script
param(
    [string]$BuildType = "debug"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       ARGUS ATTENDANCE - ANDROID APK BUILDER             " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$MobileDir = Join-Path $ScriptDir "mobile-app"
$AndroidDir = Join-Path $MobileDir "android"
$OutputDir = "E:\ARGUS TECHNOLOGIES\APK Builds"

if (-not (Test-Path $MobileDir)) {
    Write-Error "Mobile app directory not found at $MobileDir"
    exit 1
}

# 1. Sync web assets
Write-Host "`n[1/3] Syncing Capacitor Web Assets & Config..." -ForegroundColor Yellow
Set-Location $MobileDir
npx cap sync android

# 2. Build APK via Gradle
Write-Host "`n[2/3] Compiling Standalone Android APK ($BuildType)..." -ForegroundColor Yellow
Set-Location $AndroidDir

if ($BuildType -eq "release") {
    .\gradlew.bat assembleRelease --no-daemon
    $ApkSource = Join-Path $AndroidDir "app\build\outputs\apk\release\app-release-unsigned.apk"
    if (-not (Test-Path $ApkSource)) {
        $ApkSource = Join-Path $AndroidDir "app\build\outputs\apk\release\app-release.apk"
    }
} else {
    .\gradlew.bat assembleDebug --no-daemon
    $ApkSource = Join-Path $AndroidDir "app\build\outputs\apk\debug\app-debug.apk"
}

# 3. Copy to destination
Write-Host "`n[3/3] Exporting APK..." -ForegroundColor Yellow
if (Test-Path $ApkSource) {
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }
    $DestPath = Join-Path $OutputDir "Argus Attendance Kiosk.apk"
    Copy-Item -Path $ApkSource -Destination $DestPath -Force
    $ApkSizeMB = [math]::Round((Get-Item $DestPath).Length / 1MB, 2)
    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host " SUCCESS: APK Generated Successfully!" -ForegroundColor Green
    Write-Host " File: $DestPath" -ForegroundColor Green
    Write-Host " Size: $ApkSizeMB MB" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} else {
    Write-Error "APK file not found at $ApkSource"
    exit 1
}

Set-Location $ScriptDir
