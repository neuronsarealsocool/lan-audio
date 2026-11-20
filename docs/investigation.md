# Investigation boundary and findings

Investigation date: 20 November 2026. The requested reference was [WiFiAudio](https://wifiaudio.in/), Android package `com.vnd.wifi_audio`, installed version 2.2 / code 49, minimum SDK 29 and target SDK 35. The website describes PC audio streaming to an Android wireless speaker.

## Observations

1. ADB identified the test device as a Samsung SM-A125F (Galaxy A12), Android 12 / SDK 31. REA CLI `inspect-adb-device` evidence: `ev_eaec7fe81f0336061c5e6397d09fff433ab39bef065ff4e746ee47365dd91fd2`. Serial, network addresses and device screenshots are kept outside this repository.
2. ADB launched the installed reference app and screen capture showed Bass Boost, Wireless MIC, Ignore Multicast, AutoSync, an IP display and connection status. Opening How to Use led to the reference website. These observations do not demonstrate the behavior of every feature.
3. Android SDK `aapt dump xmltree` of the installed base APK showed Wi-Fi/network permissions, RECORD_AUDIO and billing. It declared no `WAKE_LOCK`, no `FOREGROUND_SERVICE` permission and no media playback foreground service. The listed services were transport/backend/job infrastructure. This is a manifest observation, not proof of all runtime behavior.
4. REA's native export inspector identified the ARM64 `libwifi.so` with SHA-256 `d28ae8e144253bcf2649340e6126857980b9ee64f8e4b64122ab82b27e70867a`. Parent evidence: `ev_293463d5b6269b94919f7824a4660feed1ce2cfd2d076814717533da7d0bce75` (summary projection `ev_cfa6dad15ec0cca1856f26a71b3221f7dc7426e0f336d943b603e130e49d0444`). The export table includes JNI methods for decode/configuration, mute, multicast, bass and packet counting. Export presence alone does not prove reachability.
5. REA's Windows Ghidra adapter rejected ELF with `target_format_unsupported` (its Windows P0 route supports PE/MZ and selected raw targets). Direct Ghidra 12.1.4 headless import succeeded as `AARCH64:LE:64:v8A:default`, preserving a local analysis project outside this repository.
6. Ghidra static decompilation at analysis address `00112a14` (`init_sockets`) showed IPv4 UDP bind with a diagnostic naming port 32000. At `00113354`, the JNI decode entry creates a 48 kHz stereo Opus decoder, selects input sockets, receives datagrams, attempts Android MediaCodec decoding and has a libopus software fallback. Output uses OpenSL ES interfaces. These are static observations; they are not packet captures or proof of protocol compatibility.

## Inference and design choice

The missing declared foreground playback service / wake permission is a plausible contributor to background suspension. This investigation did not reproduce the user's exact original dropout, establish its sole cause, or measure the original app's CPU/battery use.

LAN Audio implements the requested core PC-to-phone speaker behavior independently. It uses framework AudioTrack and a foreground service with explicit lifecycle ownership. Its first protocol is a documented PCM format with its own sender, so it requires no original binary, artwork or code. Choosing PCM reduces codec implementation complexity and keeps the APK small; it costs bandwidth relative to Opus. Initial device testing showed enough UDP gaps to add TCP as the default transport; UDP remains optional.

## Unresolved

- Full original packet/discovery/multicast format and original desktop-helper compatibility.
- Original Java lifecycle / activity callbacks: REA's JADX provider was not configured; no Java decompilation was performed.
- Real-world overnight / thermal / battery behavior, Android versions beyond the test device, and Samsung sleeping policy under long idle conditions.
- Reference microphone, bass boost and AutoSync semantics are outside this first implementation.

The website's desktop download hit a browser challenge in the command-line client. No challenge bypass or desktop-helper execution was performed. Original APKs, native libraries, private UI captures and decompiler output remain local outside the public repository.

Android design references: [background playback](https://developer.android.com/media/media3/session/background-playback), [CPU and Wi-Fi wake locks](https://developer.android.com/media/platform/mediaplayer/background), [AGP 9.2 toolchain compatibility](https://developer.android.com/build/releases/agp-9-2-0-release-notes).
