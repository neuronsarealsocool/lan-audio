"""Local GUI preferences and current-user Windows sign-in registration."""
import json
import os
from pathlib import Path
import subprocess
import sys

RUN_NAME='LAN Audio Sender'
RUN_KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'

def settings_dir():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()))/'LANAudio'

def load_settings():
    try:
        data=json.loads((settings_dir()/'settings.json').read_text(encoding='utf-8'))
        if not isinstance(data,dict):return {}
        return data
    except (OSError,ValueError):return {}

def save_settings(data):
    folder=settings_dir();folder.mkdir(parents=True,exist_ok=True)
    temporary=folder/'settings.tmp'
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
    temporary.replace(folder/'settings.json')

def launch_command(background=False):
    if getattr(sys,'frozen',False): command=[sys.executable]
    else:
        python=Path(sys.executable).with_name('pythonw.exe')
        command=[str(python if python.exists() else sys.executable),str(Path(__file__).with_name('gui.py'))]
    if background:command.append('--background')
    return command

def startup_command():return subprocess.list2cmdline(launch_command(True))

def startup_enabled():
    if sys.platform!='win32':return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
            return winreg.QueryValueEx(key,RUN_NAME)[0]==startup_command()
    except OSError:return False

def set_startup(enabled):
    if sys.platform!='win32':raise OSError('Windows sign-in startup is available on Windows only.')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:
        if enabled:winreg.SetValueEx(key,RUN_NAME,0,winreg.REG_SZ,startup_command())
        else:
            try:winreg.DeleteValue(key,RUN_NAME)
            except FileNotFoundError:pass
