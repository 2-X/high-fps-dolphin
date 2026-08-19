# Launch the real BSMSO dedicated server on Windows.
# Prints "Server listening on TCP+UDP port 27015" when ready.
# Expects ..\bundle-server\ next to this script's parent (same layout as the Mac:
# sunshine\bsmso\bundle-server\ is gitignored — unzip the handed-over bundle there).
$ErrorActionPreference = "Stop"
$bundle = Join-Path $PSScriptRoot "..\bundle-server"
if (-not (Test-Path (Join-Path $bundle "SMSO.ServerHost.dll"))) {
    Write-Error "bundle-server not found at $bundle — unzip bundle-server.zip there first (see SYNC-240.md)."
}
Set-Location $bundle
& dotnet SMSO.ServerHost.dll @args
