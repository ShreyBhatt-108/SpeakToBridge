param([string]$Python = "", [string]$EnvironmentPath = "")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $EnvironmentPath) { $EnvironmentPath = $env:SPEAK_TO_BRIDGE_AMD_ENV }
if (-not $EnvironmentPath) {
    $EnvironmentPath = Join-Path ([Environment]::GetFolderPath("UserProfile")) ".venvs\amd-rocm-10.1-py314"
}
$venvDir = [System.IO.Path]::GetFullPath($EnvironmentPath)

function Invoke-CheckedPython {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed (exit $LASTEXITCODE)." }
}

Write-Host "Requires Windows 11, x64 Python 3.14, and AMD's ROCm-compatible graphics driver."
Write-Host "Shared AMD environment: $venvDir"
$amdPython = Join-Path $venvDir "Scripts\python.exe"
if (Test-Path -LiteralPath $amdPython) {
    Invoke-CheckedPython $amdPython @("-c", "import sys, struct; assert sys.version_info[:2] == (3, 14) and sys.version_info[:3] >= (3, 14, 8) and struct.calcsize('P') == 8, 'Existing environment must use x64 Python 3.14'")
    Write-Host "Reusing existing environment."
} elseif ($Python) {
    Invoke-CheckedPython $Python @("-c", "import sys, struct; assert sys.version_info[:2] == (3, 14) and sys.version_info[:3] >= (3, 14, 8) and struct.calcsize('P') == 8, 'Requires x64 Python 3.14'")
    Invoke-CheckedPython $Python @("-m", "venv", $venvDir)
} else {
    & py -3.14 -c "import struct; assert struct.calcsize('P') == 8, 'Requires x64 Python'"
    if ($LASTEXITCODE -ne 0) { throw "Install x64 Python 3.14, then run this script again." }
    & py -3.14 -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "Could not create AMD environment." }
}
$amdPython = Join-Path $venvDir "Scripts\python.exe"
# Install pinned pure-Python/runtime dependencies before building AMD's tiny
# metadata package. Disable build isolation so its setuptools is pinned too.
Invoke-CheckedPython $amdPython @("-m", "pip", "install", "--require-hashes", "-r", (Join-Path $projectRoot "requirements-amd.lock.txt"))
Invoke-CheckedPython $amdPython @("-m", "pip", "install", "--no-deps", "--no-build-isolation", "--require-hashes", "-r", (Join-Path $projectRoot "requirements-rocm.lock.txt"))
Invoke-CheckedPython $amdPython @("-m", "pip", "check")
Invoke-CheckedPython $amdPython @((Join-Path $PSScriptRoot "check_hardware.py"), "--require-amd")
Write-Host "AMD environment ready. Launch the updated app with scripts\launch_amd.ps1."
