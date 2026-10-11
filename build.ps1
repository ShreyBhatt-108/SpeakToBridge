param([switch]$AmdRuntime)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$pythonCmd = if ($env:SPEAK_TO_BRIDGE_BUILD_PYTHON) { $env:SPEAK_TO_BRIDGE_BUILD_PYTHON } else { "python" }
Write-Host "Build Python command: $pythonCmd"
$appVersion = & $pythonCmd -c "from SpeakToBridge.constants import APP_VERSION; print(APP_VERSION)"
if (-not $appVersion) {
    throw "Unable to read the Speak to Bridge version."
}
$appVersion = $appVersion.Trim()

$pythonArch = & $pythonCmd -c "import platform, struct; print(platform.machine() + '|' + str(struct.calcsize('P') * 8))"
$pythonArchParts = $pythonArch.Trim().Split("|")
$machine = $pythonArchParts[0]
$pointerBits = $pythonArchParts[1]

Write-Host "Build Python architecture: machine=$machine, bits=$pointerBits"

if ($pointerBits -ne "64") {
    throw "SpeakToBridge Windows releases must be built with 64-bit Python."
}

if ($machine -notin @("AMD64", "x86_64", "ARM64", "aarch64")) {
    throw "Unsupported 64-bit Python architecture '$machine'. Build with x64 or ARM64 Python."
}

$installerName = if ($AmdRuntime) { "SpeakToBridge-AMD-Setup" } else { "SpeakToBridge-Setup" }
foreach ($relative in @("build", "dist\SpeakToBridge")) {
    $target = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $relative))
    if (-not $target.StartsWith($PSScriptRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Build cleanup path is outside the project: $target"
    }
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
}
Remove-Item -LiteralPath ".\dist\$installerName.exe" -Force -ErrorAction SilentlyContinue

& $pythonCmd -m pip install --require-hashes -r ".\requirements.lock.txt"
if ($LASTEXITCODE -ne 0) { throw "Runtime dependency installation failed." }
& $pythonCmd -m pip install --require-hashes -r ".\build-requirements.lock.txt"
if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }
$backendArgs = @("--exclude-module", "torch", "--exclude-module", "transformers")
if ($AmdRuntime) {
    # Reconcile Transformers' Hub dependency after installing the CPU lockfile.
    & $pythonCmd -m pip install -r ".\requirements-amd.txt"
    if ($LASTEXITCODE -ne 0) { throw "AMD model dependency installation failed." }
    & $pythonCmd -c "import torch; from transformers import WhisperProcessor, WhisperForConditionalGeneration; assert torch.version.hip, 'Install official ROCm PyTorch before building an AMD installer'; print('Bundling ROCm', torch.version.hip)"
    if ($LASTEXITCODE -ne 0) { throw "AMD runtime verification failed." }
    $backendArgs = @("--collect-all", "torch", "--collect-all", "transformers")
    $sdkPackages = & $pythonCmd -c "import importlib.metadata as m; print('\n'.join(sorted({p.split('/')[0] for d in m.distributions() if d.metadata['Name'].lower().replace('_','-').startswith('rocm') for p in map(str, d.files or []) if p.split('/')[0].startswith('_rocm')})))"
    if ($LASTEXITCODE -ne 0) { throw "Could not discover ROCm SDK packages." }
    foreach ($sdkPackage in $sdkPackages) {
        if ($sdkPackage.Trim()) { $backendArgs += @("--collect-all", $sdkPackage.Trim()) }
    }
}
& $pythonCmd -m pip check
if ($LASTEXITCODE -ne 0) { throw "Dependency verification failed." }
& $pythonCmd -m PyInstaller --noconfirm --windowed --onedir --noupx --name SpeakToBridge --specpath ".\build" @backendArgs `
    --collect-data faster_whisper `
    --add-data "SpeakToBridge\dictation_begin.wav;SpeakToBridge" `
    --add-data "SpeakToBridge\reverse_dictation_end.mp3;SpeakToBridge" `
    --add-data "SpeakToBridge\status_processing.mp3;SpeakToBridge" `
    --add-data "SpeakToBridge\status_success.mp3;SpeakToBridge" `
    --add-data "SpeakToBridge\status_failure.mp3;SpeakToBridge" `
    .\launcher.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

if (-not (Test-Path ".\dist\SpeakToBridge\SpeakToBridge.exe")) {
    throw "Build failed: .\dist\SpeakToBridge\SpeakToBridge.exe was not created."
}

$portAudioDir = ".\dist\SpeakToBridge\_internal\_sounddevice_data\portaudio-binaries"
$soundDeviceVersion = & $pythonCmd -c "import sounddevice; print(sounddevice.__version__)"
$pythonWheelVersion = & $pythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$portAudioDllName = if ($machine -in @("ARM64", "aarch64")) {
    "libportaudioarm64.dll"
} else {
    "libportaudio64bit.dll"
}
$expectedPortAudio = Join-Path $portAudioDir $portAudioDllName

if (-not (Test-Path $expectedPortAudio)) {
    Write-Warning "Expected PortAudio binary '$portAudioDllName' was not packaged automatically. Fetching the matching official sounddevice wheel."

    $wheelPlatform = if ($machine -in @("ARM64", "aarch64")) { "win_arm64" } else { "win_amd64" }
    $wheelDir = Join-Path $env:TEMP "SpeakToBridge-sounddevice-wheel"
    $wheelDir = [System.IO.Path]::GetFullPath($wheelDir)
    $tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $wheelDir.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe wheel cleanup path." }
    Remove-Item -LiteralPath $wheelDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $wheelDir | Out-Null

    & $pythonCmd -m pip download `
        --only-binary=:all: `
        --no-deps `
        --platform $wheelPlatform `
        --implementation py `
        --python-version $pythonWheelVersion `
        --abi none `
        --dest $wheelDir `
        "sounddevice==$soundDeviceVersion"

    $wheelPath = Get-ChildItem -Path $wheelDir -Filter "*.whl" | Select-Object -First 1
    if (-not $wheelPath) {
        throw "Build failed: could not download the $wheelPlatform sounddevice wheel for version $soundDeviceVersion."
    }

    & $pythonCmd -c "import sys, zipfile; from pathlib import Path; wheel=Path(sys.argv[1]); target=Path(sys.argv[2]); dll=sys.argv[3]; target.mkdir(parents=True, exist_ok=True); archive=zipfile.ZipFile(wheel); member=next((name for name in archive.namelist() if name.endswith('/portaudio-binaries/' + dll)), None); assert member, f'{dll} missing from {wheel.name}'; target.joinpath(dll).write_bytes(archive.read(member))" `
        $wheelPath.FullName `
        $portAudioDir `
        $portAudioDllName
}

if (-not (Test-Path $expectedPortAudio)) {
    throw "Build failed: expected PortAudio binary was not packaged at '$expectedPortAudio'."
}

function Find-SignTool {
    $windowsKits = "C:\Program Files (x86)\Windows Kits\10\bin"
    if (-not (Test-Path $windowsKits)) {
        return $null
    }
    return Get-ChildItem -Path $windowsKits -Filter "signtool.exe" -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
}

$signingThumbprint = $env:SPEAK_TO_BRIDGE_SIGNING_CERT_SHA1
$signTool = $null
if ($signingThumbprint) {
    $signTool = Find-SignTool
    if (-not $signTool) {
        throw "SPEAK_TO_BRIDGE_SIGNING_CERT_SHA1 is set, but signtool.exe was not found."
    }
    & $signTool.FullName sign /sha1 $signingThumbprint /fd SHA256 /tr "http://timestamp.digicert.com" /td SHA256 `
        ".\dist\SpeakToBridge\SpeakToBridge.exe"
    if ($LASTEXITCODE -ne 0) {
        throw "Code signing failed for SpeakToBridge.exe."
    }
}

$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)

$iscc = $null
foreach ($candidate in $isccCandidates) {
    if (Test-Path $candidate) {
        $iscc = $candidate
        break
    }
}

if (-not $iscc) {
    Write-Warning "Inno Setup not found. EXE build completed, installer skipped."
    Write-Host "EXE: .\dist\SpeakToBridge\SpeakToBridge.exe"
    Write-Host "Install Inno Setup 6, then run: `"$pwd\build.ps1`" again to generate installer."
    exit 0
}

& $iscc "/DAppVersion=$appVersion" "/DOutputName=$installerName" ".\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }

if (-not (Test-Path ".\dist\$installerName.exe")) {
    throw "Installer build failed: .\dist\$installerName.exe was not created."
}

if ($signingThumbprint) {
    & $signTool.FullName sign /sha1 $signingThumbprint /fd SHA256 /tr "http://timestamp.digicert.com" /td SHA256 `
        ".\dist\$installerName.exe"
    if ($LASTEXITCODE -ne 0) {
        throw "Code signing failed for SpeakToBridge-Setup.exe."
    }
}

Write-Host "EXE build completed: .\dist\SpeakToBridge\SpeakToBridge.exe"
Write-Host "Installer completed: .\dist\$installerName.exe"
