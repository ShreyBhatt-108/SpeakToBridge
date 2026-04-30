$ErrorActionPreference = "Stop"

python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name SeverusAI .\launcher.py

if (-not (Test-Path ".\dist\SeverusAI.exe")) {
    throw "Build failed: .\dist\SeverusAI.exe was not created."
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
    Write-Host "EXE: .\dist\SeverusAI.exe"
    Write-Host "Install Inno Setup 6, then run: `"$pwd\build.ps1`" again to generate installer."
    exit 0
}

& $iscc ".\installer.iss"

if (-not (Test-Path ".\dist\SeverusAI-Setup.exe")) {
    throw "Installer build failed: .\dist\SeverusAI-Setup.exe was not created."
}

Write-Host "EXE build completed: .\dist\SeverusAI.exe"
Write-Host "Installer completed: .\dist\SeverusAI-Setup.exe"
