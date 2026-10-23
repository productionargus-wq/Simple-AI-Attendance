# Create Code Signing Certificate for ARGUS TECHNOLOGIES
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=ARGUS TECHNOLOGIES" -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddYears(5)
Write-Host "Created Certificate with Thumbprint: $($cert.Thumbprint)"

# Also add to Trusted Root Certification Authorities for Current User so this PC trusts it completely
$rootStore = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
$rootStore.Open("ReadWrite")
$rootStore.Add($cert)
$rootStore.Close()
Write-Host "Installed in CurrentUser Trusted Root Store."

# Sign both the Setup Installer and the Portable Executable
$sigSetup = Set-AuthenticodeSignature -FilePath "dist\ArgusAttendance_Setup_v2.0.exe" -Certificate $cert
Write-Host "ArgusAttendance_Setup_v2.0.exe signature status: $($sigSetup.Status)"

$sigExe = Set-AuthenticodeSignature -FilePath "dist\ArgusAttendance.exe" -Certificate $cert
Write-Host "ArgusAttendance.exe signature status: $($sigExe.Status)"

# Verify signature details
$sigCheck = Get-AuthenticodeSignature "dist\ArgusAttendance_Setup_v2.0.exe"
Write-Host "Signer Subject: $($sigCheck.SignerCertificate.Subject)"
Write-Host "StatusMessage: $($sigCheck.StatusMessage)"
