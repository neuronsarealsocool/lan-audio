param(
    [string]$InstallDirectory = "$env:LOCALAPPDATA/Programs/LAN Audio",
    [switch]$StartWithWindows
)
$ErrorActionPreference='Stop'
$sourceExe=Join-Path $PSScriptRoot 'LAN Audio.exe'
if(!(Test-Path -LiteralPath $sourceExe)){throw 'Extract the Windows release ZIP first; LAN Audio.exe must be beside this installer.'}
$destination=[IO.Path]::GetFullPath($InstallDirectory)
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$installedExe=Join-Path $destination 'LAN Audio.exe'
if([IO.Path]::GetFullPath($sourceExe) -ne [IO.Path]::GetFullPath($installedExe)){Copy-Item -LiteralPath $sourceExe -Destination $installedExe -Force}
$shell=New-Object -ComObject WScript.Shell
foreach($folder in @([Environment]::GetFolderPath('Desktop'),(Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'))) {
    $shortcut=$shell.CreateShortcut((Join-Path $folder 'LAN Audio.lnk'))
    $shortcut.TargetPath=$installedExe;$shortcut.WorkingDirectory=$destination;$shortcut.IconLocation="$installedExe,0"
    $shortcut.Description='Send Windows sound to your Android phone';$shortcut.Save()
}
if($StartWithWindows) {
    $key='HKCU:/Software/Microsoft/Windows/CurrentVersion/Run'
    New-Item -Path $key -Force | Out-Null
    New-ItemProperty -Path $key -Name 'LAN Audio Sender' -Value ('"'+$installedExe+'" --background') -PropertyType String -Force | Out-Null
}
Write-Output "Installed: $installedExe"
Write-Output 'Created desktop and Start menu shortcuts. Audio capture starts only after Start audio, unless you enable automatic audio in the GUI.'
