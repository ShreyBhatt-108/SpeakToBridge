param([string]$Python = "", [string]$EnvironmentPath = "")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $EnvironmentPath) { $EnvironmentPath = $env:SPEAK_TO_BRIDGE_AMD_ENV }
if (-not $EnvironmentPath) {
    $EnvironmentPath = Join-Path ([Environment]::GetFolderPath("UserProfile")) ".venvs\amd-rocm-7.2.1-py312"
}
$venvDir = [System.IO.Path]::GetFullPath($EnvironmentPath)

function Invoke-CheckedPython {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed (exit $LASTEXITCODE)." }
}

Write-Host "Requires Windows 11, x64 Python 3.12, and AMD's ROCm-compatible graphics driver."
Write-Host "Shared AMD environment: $venvDir"
$amdPython = Join-Path $venvDir "Scripts\python.exe"
if (Test-Path -LiteralPath $amdPython) {
    Invoke-CheckedPython $amdPython @("-c", "import sys, struct; assert sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8, 'Existing environment must use x64 Python 3.12'")
    Write-Host "Reusing existing environment."
} elseif ($Python) {
    Invoke-CheckedPython $Python @("-c", "import sys, struct; assert sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8, 'Requires x64 Python 3.12'")
    Invoke-CheckedPython $Python @("-m", "venv", $venvDir)
} else {
    & py -3.12 -c "import struct; assert struct.calcsize('P') == 8, 'Requires x64 Python'"
    if ($LASTEXITCODE -ne 0) { throw "Install x64 Python 3.12, then run this script again." }
    & py -3.12 -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "Could not create AMD environment." }
}
$amdPython = Join-Path $venvDir "Scripts\python.exe"
Invoke-CheckedPython $amdPython @("-m", "pip", "install", "--upgrade", "pip")
Invoke-CheckedPython $amdPython @("-m", "pip", "install", "--require-hashes", "-r", (Join-Path $projectRoot "requirements.lock.txt"))
$repo = "https://repo.radeon.com/rocm/windows/rocm-rel-7.2.1"
Invoke-CheckedPython $amdPython @("-m", "pip", "install", "--no-cache-dir",
    "$repo/rocm_sdk_core-7.2.1-py3-none-win_amd64.whl",
    "$repo/rocm_sdk_devel-7.2.1-py3-none-win_amd64.whl",
    "$repo/rocm_sdk_libraries_custom-7.2.1-py3-none-win_amd64.whl",
    "$repo/rocm-7.2.1.tar.gz")
Invoke-CheckedPython $amdPython @("-m", "pip", "install", "--no-cache-dir",
    "$repo/torch-2.9.1%2Brocm7.2.1-cp312-cp312-win_amd64.whl")
Invoke-CheckedPython $amdPython @("-m", "pip", "install", "-r", (Join-Path $projectRoot "requirements-amd.txt"))
Invoke-CheckedPython $amdPython @("-m", "pip", "check")
Invoke-CheckedPython $amdPython @((Join-Path $PSScriptRoot "check_hardware.py"), "--require-amd")
Write-Host "AMD environment ready. Launch the updated app with scripts\launch_amd.ps1."
