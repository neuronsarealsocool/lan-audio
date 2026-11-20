# Desktop sender

## Windows app

Download the Windows ZIP from the repository Releases, extract it and open **LAN Audio.exe**. It bundles Python and the audio dependencies; Windows 10/11 x64 is the supported desktop target. Enter the address displayed on the phone, start the phone speaker, then use **Test tone · 5 sec** or **Start audio**. **Stop** ends capture. The tray menu also has Stop and Quit.

The bundled `install-windows.ps1` copies the executable to your user Programs folder and adds desktop / Start menu shortcuts. It needs no administrator rights:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-windows.ps1 -StartWithWindows
```

Use **Open in the tray at Windows sign-in** to turn login startup on or off. **Start audio automatically when the app opens** separately opts into automatic system-output capture; it is off by default. Automatic reconnect applies only while Start audio remains active. Close hides the app to the tray, and relaunching the shortcut restores the existing window. Quit stops capture and exits.

Settings and a short diagnostic text log live in `%LOCALAPPDATA%/LANAudio`. The log does not contain recorded audio. The installer registers only the current user's `LAN Audio Sender` Run entry. Remove that entry through the checkbox before deleting/moving an installed executable. No scheduled task or service is installed. The preview executable is unsigned.

Run from source with `python -m pip install -r desktop/requirements-gui.txt`, then `python desktop/gui.py`. Build on Windows with Python 3.14, `desktop/requirements-build.txt` and `desktop/build-windows.ps1`; output is `desktop/dist/LAN Audio.exe`.

## Command-line sender

The sender streams Windows speaker output to the Android receiver. It starts only
when you run the command, exits with Ctrl+C, and never captures a microphone.
The test-tone path needs only Python's standard library and works across platforms.

Use Python 3.11 or newer. From the repository root:

```powershell
python desktop/sender.py --host PHONE_IP --tone --duration 10
python -m pip install -r desktop/requirements.txt
python desktop/sender.py --list-devices
python desktop/sender.py --host PHONE_IP
```

Tap **Start speaker** on the phone first. Replace `PHONE_IP` with its Wi-Fi IPv4
address; both devices must be on the same trusted LAN. If necessary, allow Python
on your Windows private network and permit TCP port 48100. Guest Wi-Fi client
isolation can prevent devices from communicating.

TCP is the default transport. It uses `TCP_NODELAY`, a three-second connection
timeout and a one-second send timeout. It preserves frames across Wi-Fi loss by
retransmitting, but a poor connection can add latency or time out. Restart the
sender after a disconnection. To experiment with UDP, which can drop audio rather
than wait for retransmissions:

```powershell
python desktop/sender.py --host PHONE_IP --transport udp --tone --duration 10
```

UDP also uses port 48100.

Capture uses the default WASAPI speaker loopback device. To choose another:

```powershell
python desktop/sender.py --host PHONE_IP --device 12 --duration 60
```

Replace `12` with an index from `--list-devices`. The output must support 48 kHz,
stereo, 16-bit PCM. If opening it fails, select 48 kHz in Windows sound device
properties or choose another output device. Device changes during capture require
restarting the sender. The sender currently does not resample, mix surround audio,
discover phones automatically, or reconnect to a changed phone IP.

Audio is uncompressed and unencrypted: about 1.57 Mbit/s before network overhead,
200 framed blocks/second. Use trusted private Wi-Fi; do not expose the receiver's
port on the internet. No audio is written to disk or uploaded to a service.

The capture callback queues at most eight chunks (normally 40 ms), dropping old
chunks when the sender stalls. Packet pacing prevents a suspended process from
flooding the network with catch-up audio. This is a prototype, not a guarantee of
uninterrupted playback under Windows scheduling or network loss.

Run wire-format and real localhost UDP smoke tests:

```powershell
python -m unittest discover -s desktop -v
```

Capture depends on [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch), a
Windows WASAPI loopback extension of PyAudio. Test tone and protocol tests do not
import or install it. Tests exercise actual TCP byte-stream reassembly/pacing and
UDP datagram delivery on localhost.
