# LAN Audio

An independent, lightweight Android Wi-Fi speaker and Windows system-audio sender, built to reuse older phones with their screen off.

**Early prototype.** It uses its own documented protocol and bundled sender. It is not a patched WiFiAudio APK, is not affiliated with WiFiAudio, and does not currently work with WiFiAudio's desktop helper. No original app code, libraries, artwork, or APKs are distributed here.

## Try it

1. Install the APK from [Releases](https://github.com/neuronsarealsocool/lan-audio/releases). Preview APKs are debug signed; install only if you trust this project.
2. Put the PC and phone on the same private Wi-Fi network.
3. Open **LAN Audio** on the phone. The speaker starts automatically by default, using your saved sender restriction if set; the phone displays its destination IP and port. **Start speaker when app opens** can be switched off for manual control.
4. On Windows, download the Windows ZIP from [Releases](https://github.com/neuronsarealsocool/lan-audio/releases), extract it and open **LAN Audio.exe**. No Python installation is needed. Enter the phone address, click **Test tone**, then **Start audio** to send system sound. **Stop** ends capture. Close hides it to the tray; **Quit** exits.
5. To create desktop / Start menu shortcuts, run the bundled `install-windows.ps1` from PowerShell. Add `-StartWithWindows` to enable sign-in startup, or toggle **Open in the tray at Windows sign-in** inside the GUI. **Start audio automatically when the app opens** is a separate opt-in setting; capture is off by default. The GUI remembers the phone address and can reconnect while Start is active.

The command-line sender is still in `desktop/sender.py`. To test without capturing audio:

   ```powershell
   python desktop/sender.py --host PHONE_IP --tone --duration 10
   ```

For command-line Windows system output, install Python 3.11+ and the capture dependency, then start the sender explicitly:

   ```powershell
   python -m venv .venv
   .venv/Scripts/python.exe -m pip install -r desktop/requirements.txt
   .venv/Scripts/python.exe desktop/sender.py --host PHONE_IP
   ```

The Windows sender captures the selected system output, including any audio playing on that output. The GUI's Stop ends capture; Ctrl+C stops the CLI. **Stop speaker** in the Android app or **Stop** in its notification stops receiving and releases CPU / Wi-Fi locks. Use the matching sender for this app.

## Background behavior

- Opening the Android app starts its `mediaPlayback` foreground service by default. Returning to the app after leaving it readies the speaker again; rotating the current screen preserves an explicit Stop. The service owns audio independently of the activity.
- A persistent notification and media session provide a Stop control.
- Partial CPU and Wi-Fi locks keep the receiver ready while the speaker session is on. The CPU lock has a renewable timeout; both locks are released on Stop. This intentionally uses battery while armed, even when the sender is silent.
- Audio focus is released after input goes idle. Permanent loss of focus ends the session; transient loss mutes output until focus returns.
- TCP is the default transport to avoid the datagram loss observed on the test phone. UDP is available with `--transport udp`. Network receive and playback run on separate threads. A bounded buffer reorders packets, conceals short gaps with silence, and re-buffers after sustained underflow instead of replaying an ever-growing backlog.
- Network traffic and audio stop with the service. There is no boot auto-start or hidden restart after force-stop / process death; opening the app again starts a new session.

On Samsung phones, remove the app from **Sleeping apps** / **Deep sleeping apps** if needed. The **Battery settings** button opens Android settings; battery exemption is optional. A foreground service improves lifecycle reliability but cannot guarantee survival under every OEM policy or memory condition.

## Current limits

- Android 6+; device testing currently covers a Samsung Galaxy A12 running Android 12. Other Android versions need device validation.
- Windows system-output capture only. The test tone works on other Python-supported desktop systems.
- Stereo 48 kHz PCM16 over TCP by default, or unicast UDP: about 1.54 Mbit/s of audio plus headers. Both listen on port 48100. The buffer favors reliability over minimal latency (120 ms pre-roll plus device output and network delay).
- Trusted LAN only: audio is unencrypted and unauthenticated. The optional IPv4 restriction and active endpoint pin reduce accidental interference; they are not cryptographic pairing. Do not expose port 48100 to the internet.
- No discovery, multicast, Opus compression, microphone return channel, bass boost, or original-helper compatibility yet.
- Short device checks are not an overnight reliability or battery benchmark. See [validation](docs/validation.md).

## Build and test

Requires JDK 17+, Android SDK platform 35, and network access for Gradle dependencies. Set `ANDROID_HOME` or create an ignored `local.properties` with `sdk.dir`.

```powershell
./gradlew.bat testDebugUnitTest lintDebug assembleDebug
python -m unittest discover -s desktop -p "test_*.py" -v
```

On Linux / macOS use `bash gradlew` (or make `gradlew` executable). The wrapper pins Gradle 9.4.1 with Android Gradle plugin 9.2.1. APK: `app/build/outputs/apk/debug/app-debug.apk`.

To run the GUI from source, install `desktop/requirements-gui.txt` and run `python desktop/gui.py`. To package on Windows, install `desktop/requirements-build.txt` and run `desktop/build-windows.ps1`. The shared icon is generated by `scripts/make_icons.py` from code-native geometry and includes Android legacy/adaptive/monochrome and Windows ICO resources.

See [desktop instructions](desktop/README.md), [protocol](docs/protocol.md), and [investigation findings](docs/investigation.md).

## License

MIT for the source in this repository. Dependencies retain their own licenses. Original WiFiAudio artifacts are not part of this repository.
