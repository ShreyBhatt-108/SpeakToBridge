param([string]$EnvironmentPath = "")
$ErrorActionPreference = "Stop"
if (-not $EnvironmentPath) { $EnvironmentPath = $env:SPEAK_TO_BRIDGE_AMD_ENV }
if (-not $EnvironmentPath) {
    $EnvironmentPath = Join-Path ([Environment]::GetFolderPath("UserProfile")) ".venvs\amd-rocm-10.1-py314"
}
$activate = Join-Path $EnvironmentPath "Scripts\Activate.ps1"
if (-not (Test-Path -LiteralPath $activate)) { throw "Run scripts\setup_amd.ps1 first." }
. $activate
$env:SPEAK_TO_BRIDGE_AMD_ENV = $EnvironmentPath
# These variables apply to this terminal only. Experiments share the app cache.
$env:HF_HUB_CACHE = Join-Path $env:LOCALAPPDATA "SpeakToBridge\models"
$env:HF_HUB_DISABLE_XET = "1"
Write-Host "AMD Python: $EnvironmentPath"
Write-Host "Shared Hugging Face model cache: $env:HF_HUB_CACHE"
Write-Host "Use python for experiments; use deactivate when finished."
