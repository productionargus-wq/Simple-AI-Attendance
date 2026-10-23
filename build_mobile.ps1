# Argus AI Attendance - Mobile App Builder (APK, Play Store AAB, iOS Workspace)
param(
    [ValidateSet("apk", "aab", "ios", "all")]
    [string]$Target = "apk",
    [string]$BuildType = "release"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "    ARGUS ATTENDANCE - MULTI-PLATFORM MOBILE BUILDER      " -ForegroundColor Cyan
Write-Host "    Target: $($Target.ToUpper()) | Type: $($BuildType.ToUpper())" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$MobileDir = Join-Path $ScriptDir "mobile-app"
$AndroidDir = Join-Path $MobileDir "android"
$IosDir = Join-Path $MobileDir "ios"
$OutputDir = "E:\ARGUS TECHNOLOGIES\APK Builds"

if (-not (Test-Path $MobileDir)) {
    Write-Error "Mobile app directory not found at $MobileDir"
    exit 1
}

# 1. Sync Capacitor web assets & config for target platforms
Write-Host "`n[1/4] Syncing Capacitor Web Assets & Native Config..." -ForegroundColor Yellow
Set-Location $MobileDir
if ($Target -eq "ios") {
    npx cap sync ios
} elseif ($Target -eq "all") {
    npx cap sync
} else {
    npx cap sync android
}

# 2. Build Android APK if requested
if ($Target -in @("apk", "all")) {
    Write-Host "`n[2/4] Compiling Standalone Android APK ($BuildType)..." -ForegroundColor Yellow
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

    if (Test-Path $ApkSource) {
        $MobileDestPath = Join-Path $MobileDir "Argus Attendance.apk"
        Copy-Item -Path $ApkSource -Destination $MobileDestPath -Force
        $MobileSizeMB = [math]::Round((Get-Item $MobileDestPath).Length / 1MB, 2)

        if (-not (Test-Path $OutputDir)) {
            New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
        }
        $DestPath = Join-Path $OutputDir "Argus Attendance Kiosk.apk"
        Copy-Item -Path $ApkSource -Destination $DestPath -Force

        Write-Host " -> APK Generated: $MobileDestPath ($MobileSizeMB MB)" -ForegroundColor Green
    } else {
        Write-Warning "APK build completed but source file was not found at $ApkSource"
    }
}

# 3. Build Google Play Store AAB Bundle if requested
if ($Target -in @("aab", "all")) {
    Write-Host "`n[3/4] Compiling Google Play Store Android App Bundle (.aab)..." -ForegroundColor Yellow
    Set-Location $AndroidDir
    .\gradlew.bat bundleRelease --no-daemon
    
    $AabSource = Join-Path $AndroidDir "app\build\outputs\bundle\release\app-release.aab"
    if (-not (Test-Path $AabSource)) {
        $AabSource = Join-Path $AndroidDir "app\build\outputs\bundle\release\app-release-unsigned.aab"
    }

    if (Test-Path $AabSource) {
        $AabDestPath = Join-Path $MobileDir "Argus Attendance.aab"
        Copy-Item -Path $AabSource -Destination $AabDestPath -Force
        $AabSizeMB = [math]::Round((Get-Item $AabDestPath).Length / 1MB, 2)

        if (-not (Test-Path $OutputDir)) {
            New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
        }
        $AabBackupPath = Join-Path $OutputDir "Argus Attendance Kiosk.aab"
        Copy-Item -Path $AabSource -Destination $AabBackupPath -Force

        Write-Host " -> Play Store AAB Generated: $AabDestPath ($AabSizeMB MB)" -ForegroundColor Green
    } else {
        Write-Warning "AAB build completed but source file was not found at $AabSource"
    }
}

# 4. Package iOS Workspace if requested
if ($Target -in @("ios", "all")) {
    Write-Host "`n[4/4] Packaging Native iOS Project Workspace..." -ForegroundColor Yellow
    Set-Location $MobileDir
    $IosZipPath = Join-Path $MobileDir "Argus Attendance iOS Workspace.zip"
    Compress-Archive -Path (Join-Path $IosDir "*") -DestinationPath $IosZipPath -Force
    $IosSizeMB = [math]::Round((Get-Item $IosZipPath).Length / 1MB, 2)

    if (Test-Path $OutputDir) {
        Copy-Item -Path $IosZipPath -Destination (Join-Path $OutputDir "Argus Attendance iOS Workspace.zip") -Force
    }

    Write-Host " -> iOS Workspace Packaged: $IosZipPath ($IosSizeMB MB)" -ForegroundColor Green
}

Set-Location $ScriptDir

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " SUCCESS: Mobile Build Operations Completed!" -ForegroundColor Green
Write-Host " All build outputs are located in: $MobileDir" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
