$ErrorActionPreference = "Stop"

python -m pip install pyinstaller
python -m PyInstaller --noconfirm --windowed --onedir --name SeverusAI `
    --collect-data faster_whisper `
    --add-data "SeverusAI\dictation_begin.wav;SeverusAI" `
    --add-data "SeverusAI\reverse_dictation_end.mp3;SeverusAI" `
    .\launcher.py

if (-not (Test-Path ".\dist\SeverusAI\SeverusAI.exe")) {
    throw "Build failed: .\dist\SeverusAI\SeverusAI.exe was not created."
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
