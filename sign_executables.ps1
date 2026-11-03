# Create Code Signing Certificate for ARGUS CNC™
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=ARGUS CNC™" -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddYears(5)
Write-Host "Created Certificate with Thumbprint: $($cert.Thumbprint)"

# Also add to Trusted Root Certification Authorities for Current User so this PC trusts it completely
$rootStore = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
$rootStore.Open("ReadWrite")
$rootStore.Add($cert)
$rootStore.Close()
Write-Host "Installed in CurrentUser Trusted Root Store."

# Sign both the Setup Installer and the Portable Executable
$setupPath = if (Test-Path "dist\Argus-Attendance-Intelligence-Setup.exe") { "dist\Argus-Attendance-Intelligence-Setup.exe" } else { "dist\ArgusAttendance_Setup_v2.0.exe" }
$exePath = if (Test-Path "dist\Argus-Attendance-Intelligence.exe") { "dist\Argus-Attendance-Intelligence.exe" } else { "dist\ArgusAttendance.exe" }

$sigSetup = Set-AuthenticodeSignature -FilePath $setupPath -Certificate $cert
Write-Host "$setupPath signature status: $($sigSetup.Status)"

$sigExe = Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert
Write-Host "$exePath signature status: $($sigExe.Status)"

# Verify signature details
$sigCheck = Get-AuthenticodeSignature $setupPath
Write-Host "Signer Subject: $($sigCheck.SignerCertificate.Subject)"
Write-Host "StatusMessage: $($sigCheck.StatusMessage)"
