param([string]$Distribution = "Ubuntu-24.04", [string]$LinuxPython = "/opt/amd-ai/bin/python")
$ErrorActionPreference = "Stop"
$env:SPEAK_TO_BRIDGE_WSL_DISTRO = $Distribution
$env:SPEAK_TO_BRIDGE_WSL_PYTHON = $LinuxPython
$env:SPEAK_TO_BRIDGE_WSL_WORKER = Join-Path $PSScriptRoot "wsl_worker.py"
# Use the installed Windows app; the Linux worker imports the mounted checkout.
$app = Join-Path $env:LOCALAPPDATA "Programs\SpeakToBridge\SpeakToBridge.exe"
Start-Process -FilePath $app -WindowStyle Hidden
