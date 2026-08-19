# Super Mario Sunshine launcher - one command (Windows counterpart of ./sms).
#   powershell -ExecutionPolicy Bypass -File sms.ps1          launch the TUI
#   powershell -ExecutionPolicy Bypass -File sms.ps1 setup    first-run wizard
# Bootstraps its own venv on first run; pins deps from requirements.txt.
param([string]$Command = "")

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $dir ".venv"
$vpy = Join-Path $venv "Scripts\python.exe"

# Python 3.10+ required (textual needs match-statement syntax).
$pyver = python --version 2>&1
if ($pyver -notmatch 'Python 3\.(1[0-9]|[2-9][0-9])') {
    Write-Error "[sms] Python 3.10 or later is required (found: $pyver)."
}

if (-not (Test-Path $vpy)) {
    Write-Host "[sms] creating venv..."
    python -m venv $venv
    & $vpy -m pip -q install --upgrade pip | Out-Null
}

# Always sync deps so a fresh clone or an upgraded requirements.txt installs
# the right pinned versions without manual steps.
& $vpy -m pip -q install -r (Join-Path $dir "requirements.txt")

Set-Location $dir
if ($Command -eq "setup") {
    & $vpy -m smslaunch.setup_wizard
} else {
    & $vpy -m smslaunch
}
