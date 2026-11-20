param([string]$Python = "$PSScriptRoot/.venv/Scripts/python.exe")
$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    & $Python -m PyInstaller --noconfirm --onefile --windowed --name 'LAN Audio' --icon 'assets/lan-audio.ico' --add-data 'assets:assets' --collect-all pyaudiowpatch --hidden-import pystray._win32 gui.py
    if($LASTEXITCODE -ne 0){throw 'Windows build failed'}
} finally {Pop-Location}
