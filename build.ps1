$ErrorActionPreference = "Stop"

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

Remove-Item -Recurse -Force ".\build" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".\dist\SpeakToBridge" -ErrorAction SilentlyContinue
Remove-Item -Force ".\dist\SpeakToBridge-Setup.exe" -ErrorAction SilentlyContinue

& $pythonCmd -m pip install --require-hashes -r ".\requirements.lock.txt"
& $pythonCmd -m pip install --require-hashes -r ".\build-requirements.lock.txt"
& $pythonCmd -m PyInstaller --noconfirm --windowed --onedir --noupx --name SpeakToBridge `
    --collect-data faster_whisper `
    --add-data "SpeakToBridge\dictation_begin.wav;SpeakToBridge" `
    --add-data "SpeakToBridge\reverse_dictation_end.mp3;SpeakToBridge" `
    --add-data "SpeakToBridge\status_processing.mp3;SpeakToBridge" `
    --add-data "SpeakToBridge\status_success.mp3;SpeakToBridge" `
    --add-data "SpeakToBridge\status_failure.mp3;SpeakToBridge" `
    .\launcher.py

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
    Remove-Item -Recurse -Force $wheelDir -ErrorAction SilentlyContinue
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

& $iscc "/DAppVersion=$appVersion" ".\installer.iss"

if (-not (Test-Path ".\dist\SpeakToBridge-Setup.exe")) {
    throw "Installer build failed: .\dist\SpeakToBridge-Setup.exe was not created."
}

if ($signingThumbprint) {
    & $signTool.FullName sign /sha1 $signingThumbprint /fd SHA256 /tr "http://timestamp.digicert.com" /td SHA256 `
        ".\dist\SpeakToBridge-Setup.exe"
    if ($LASTEXITCODE -ne 0) {
        throw "Code signing failed for SpeakToBridge-Setup.exe."
    }
}

Write-Host "EXE build completed: .\dist\SpeakToBridge\SpeakToBridge.exe"
Write-Host "Installer completed: .\dist\SpeakToBridge-Setup.exe"
