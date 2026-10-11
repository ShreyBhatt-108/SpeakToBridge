$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$amdPython = Join-Path $projectRoot ".venv-amd\Scripts\pythonw.exe"
if (-not (Test-Path -LiteralPath $amdPython)) {
    throw "Run scripts\setup_amd.ps1 first."
}
Start-Process -FilePath $amdPython -ArgumentList ('"' + (Join-Path $projectRoot "launcher.py") + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden
