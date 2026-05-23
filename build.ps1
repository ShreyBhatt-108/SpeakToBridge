$ErrorActionPreference = "Stop"

$pythonCmd = if ($env:SEVERUS_BUILD_PYTHON) { $env:SEVERUS_BUILD_PYTHON } else { "python" }
Write-Host "Build Python command: $pythonCmd"

$pythonArch = & $pythonCmd -c "import platform, struct; print(platform.machine() + '|' + str(struct.calcsize('P') * 8))"
$pythonArchParts = $pythonArch.Trim().Split("|")
$machine = $pythonArchParts[0]
$pointerBits = $pythonArchParts[1]

Write-Host "Build Python architecture: machine=$machine, bits=$pointerBits"

if ($pointerBits -ne "64") {
    throw "SeverusAI Windows releases must be built with 64-bit Python."
}

if ($machine -notin @("AMD64", "x86_64", "ARM64", "aarch64")) {
    throw "Unsupported 64-bit Python architecture '$machine'. Build with x64 or ARM64 Python."
}

Remove-Item -Recurse -Force ".\build" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".\dist\SeverusAI" -ErrorAction SilentlyContinue
Remove-Item -Force ".\dist\SeverusAI-Setup.exe" -ErrorAction SilentlyContinue

& $pythonCmd -m pip install pyinstaller
& $pythonCmd -m PyInstaller --noconfirm --windowed --onedir --noupx --name SeverusAI `
    --collect-data faster_whisper `
    --add-data "SeverusAI\dictation_begin.wav;SeverusAI" `
    --add-data "SeverusAI\reverse_dictation_end.mp3;SeverusAI" `
    .\launcher.py

if (-not (Test-Path ".\dist\SeverusAI\SeverusAI.exe")) {
    throw "Build failed: .\dist\SeverusAI\SeverusAI.exe was not created."
}

$portAudioDir = ".\dist\SeverusAI\_internal\_sounddevice_data\portaudio-binaries"
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
    $wheelDir = Join-Path $env:TEMP "SeverusAI-sounddevice-wheel"
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
    Write-Host "EXE: .\dist\SeverusAI\SeverusAI.exe"
    Write-Host "Install Inno Setup 6, then run: `"$pwd\build.ps1`" again to generate installer."
    exit 0
}

& $iscc ".\installer.iss"

if (-not (Test-Path ".\dist\SeverusAI-Setup.exe")) {
    throw "Installer build failed: .\dist\SeverusAI-Setup.exe was not created."
}

Write-Host "EXE build completed: .\dist\SeverusAI\SeverusAI.exe"
Write-Host "Installer completed: .\dist\SeverusAI-Setup.exe"
