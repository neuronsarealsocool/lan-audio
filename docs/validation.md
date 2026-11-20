# Validation — 20 November 2026

This preview was built locally on Windows and installed alongside the reference app on a Samsung Galaxy A12 (SM-A125F), Android 12 / API 31. No battery exemption or Samsung sleeping-list changes were made during testing.

## Automated checks

- `gradlew testDebugUnitTest lintDebug assembleDebug`: passed. Five receiver tests cover malformed frames, pre-roll, reordering, gap concealment, uint32 wrap, bounded memory, stream isolation and recovery after a sender stall.
- `python -m unittest discover -s desktop -p 'test_*.py' -v`: six tests passed. Includes real localhost TCP reassembly/pacing and UDP delivery as well as known wire vectors, input rejection and test-tone generation.
- Android lint: zero errors, five warnings (newer SDK/Gradle availability, backup configuration and text internationalization). The APK targets API 35; newer Android devices are not yet device-tested.
- Final preview APK is debug signed. A SHA-256 file accompanies the release.

## Device and transport checks

1. Inspected the original installed app with ADB, REA and Ghidra; boundaries and evidence are in [investigation.md](investigation.md).
2. Installed LAN Audio, started its speaker through the visible UI and sent a quiet synthetic stereo tone from Windows. No real user audio was saved.
3. Pressed Home and put the screen to sleep. `dumpsys` confirmed `isForeground=true`, the partial CPU lock and the Wi-Fi lock. Android reported `mWakefulness=Dozing` during checks while decoded/written frame counters continued increasing. Some earlier runs later woke; the tests do not assume uninterrupted screen-off solely from an elapsed timer.
4. Initial UDP run: sender completed 18,000 blocks over 90 seconds. Receiver final counters before the later capture test: 17,558 accepted packets, 126 concealed blocks, 16 late packets, 20 rebuffer/resync events and 126 AudioTrack underruns. These are different counters, not a single loss percentage; rebuffering discards some accepted audio. This result motivated making TCP the default.
5. Windows WASAPI loopback capture was tested with a generated eight-second desktop tone and a five-second sender run. The capture path sent 999 blocks and the phone's counters increased. A separate silence-only capture sent zero blocks because the output device was inactive. This verifies capture/transport operation, not subjective listening quality.
6. Final TCP run: sender completed a 90-second wall-clock run with 17,939 blocks (89.70 seconds of generated audio; delayed deadlines are not flooded to catch up). Receiver counters after input settled: 17,933 accepted, 18 concealed blocks, six late packets, three buffer resync events and 16 output underruns. Through the first roughly 75 seconds, logs showed zero concealed gaps / late packets / underruns, and one initial buffer resync; an interruption near the end added the later counts. End-of-stream concealment is included in these totals. This was substantially better than the earlier UDP run in this session, but the runs are not a controlled benchmark and dropouts are still possible.
7. TCP Windows output capture with the same generated test tone also sent 999 blocks over five seconds. Both capture transports operated without saving captured system audio to disk.

## Limits of the evidence

Counters establish that traffic was received and PCM was written to AudioTrack; they are not microphone recordings or a perceptual quality assessment. Short runs do not establish overnight stability, battery drain, thermal behavior, long Wi-Fi roam behavior, reboot recovery, force-stop recovery, or newer-Android compatibility. The original app's exact background failure was not reproduced, so no comparative reliability percentage is claimed.

The app intentionally requires a new user start after process death. TCP can retransmit and add latency; broken connections require restarting the desktop sender. The buffer caps backlog and may resynchronize rather than replay stale audio.
