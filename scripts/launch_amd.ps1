param([string]$EnvironmentPath = "")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $EnvironmentPath) { $EnvironmentPath = $env:SPEAK_TO_BRIDGE_AMD_ENV }
if (-not $EnvironmentPath) {
    $legacyEnvironment = Join-Path $projectRoot ".venv-amd"
    $EnvironmentPath = if (Test-Path -LiteralPath $legacyEnvironment) { $legacyEnvironment } else {
        Join-Path ([Environment]::GetFolderPath("UserProfile")) ".venvs\amd-rocm-7.2.1-py312"
    }
}
$amdPython = Join-Path $EnvironmentPath "Scripts\pythonw.exe"
if (-not (Test-Path -LiteralPath $amdPython)) {
    throw "Run scripts\setup_amd.ps1 first."
}
Start-Process -FilePath $amdPython -ArgumentList ('"' + (Join-Path $projectRoot "launcher.py") + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden
