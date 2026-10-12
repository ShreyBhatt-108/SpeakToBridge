# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [('SpeakToBridge\\dictation_begin.wav', 'SpeakToBridge'), ('SpeakToBridge\\reverse_dictation_end.mp3', 'SpeakToBridge'), ('SpeakToBridge\\status_processing.mp3', 'SpeakToBridge'), ('SpeakToBridge\\status_success.wav', 'SpeakToBridge'), ('SpeakToBridge\\status_failure.mp3', 'SpeakToBridge')]
datas += collect_data_files('faster_whisper')


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SpeakToBridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SpeakToBridge',
)
