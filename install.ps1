$ErrorActionPreference = "Stop"
$Version = if ($env:CONVERGE_VERSION) { $env:CONVERGE_VERSION } else { "0.1.0" }
$InstallDir = if ($env:CONVERGE_INSTALL_DIR) { $env:CONVERGE_INSTALL_DIR } else { "$HOME\bin" }
$Archive = "converge-x86_64-pc-windows-msvc.zip"
$Base = "https://github.com/desenyon/converge/releases/download/v$Version"
$Temporary = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid())

New-Item -ItemType Directory -Path $Temporary | Out-Null
try {
    Invoke-WebRequest -Uri "$Base/$Archive" -OutFile "$Temporary\$Archive"
    Invoke-WebRequest -Uri "$Base/$Archive.sha256" -OutFile "$Temporary\$Archive.sha256"
    $Expected = (Get-Content "$Temporary\$Archive.sha256").Split(" ")[0].ToLowerInvariant()
    $Actual = (Get-FileHash "$Temporary\$Archive" -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Expected -ne $Actual) { throw "checksum verification failed" }
    Expand-Archive -Path "$Temporary\$Archive" -DestinationPath $Temporary
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item "$Temporary\converge.exe" "$InstallDir\converge.exe" -Force
    Write-Output "installed converge to $InstallDir\converge.exe"
} finally {
    Remove-Item -Recurse -Force $Temporary
}
