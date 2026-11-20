#!/usr/bin/env python3
"""Send explicitly started Windows system audio, or a test tone, to LAN Audio."""

import argparse
import math
import queue
import secrets
import socket
import struct
import sys
import time

from protocol import CHANNELS, FRAMES, PAYLOAD_BYTES, PORT, SAMPLE_RATE, encode_packet

INTERVAL = FRAMES / SAMPLE_RATE


def send_packet(sock: socket.socket, packet: bytes) -> None:
    """Preserve whole framing even when TCP performs a partial socket write."""
    if sock.type == socket.SOCK_STREAM:
        sock.sendall(packet)
    else:
        sock.send(packet)


def tone_chunk(first_frame: int, frequency: float = 440.0) -> bytes:
    """Quiet 8%-amplitude sine wave, with phase preserved between packets."""
    samples = (
        int(32767 * 0.08 * math.sin(2 * math.pi * frequency * (first_frame + i) / SAMPLE_RATE))
        for i in range(FRAMES)
    )
    return b"".join(struct.pack("<hh", sample, sample) for sample in samples)


def send_tone(sock: socket.socket, stream_id: int, duration: float | None) -> int:
    started = time.monotonic()
    deadline = started
    sequence = 0
    sent = 0
    while duration is None or time.monotonic() - started < duration:
        delay = deadline - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        if duration is not None and time.monotonic() - started >= duration:
            break
        send_packet(sock, encode_packet(tone_chunk(sent * FRAMES), stream_id, sequence))
        sent += 1
        sequence = (sequence + 1) & 0xFFFFFFFF
        deadline += INTERVAL
        # A suspended process resumes live; it never floods the LAN to catch up.
        if time.monotonic() - deadline > INTERVAL:
            deadline = time.monotonic() + INTERVAL
    return sent


def capture_windows(sock: socket.socket | None, stream_id: int, duration: float | None,
                    device_index: int | None, list_devices: bool) -> int:
    if sys.platform != "win32":
        raise RuntimeError("System audio capture currently supports Windows only. --tone works on other systems.")
    try:
        import pyaudiowpatch as pyaudio
    except ImportError as exc:
        raise RuntimeError("Install capture support: python -m pip install -r desktop/requirements.txt") from exc

    with pyaudio.PyAudio() as audio:
        if list_devices:
            for device in audio.get_loopback_device_info_generator():
                print(f"{device['index']}: {device['name']} (default {int(device['defaultSampleRate'])} Hz)")
            return 0
        device = (audio.get_default_wasapi_loopback() if device_index is None
                  else audio.get_device_info_by_index(device_index))
        if not device.get("isLoopbackDevice"):
            raise RuntimeError("Choose a WASAPI loopback device from --list-devices; microphone inputs are not accepted.")
        if device["maxInputChannels"] < CHANNELS:
            raise RuntimeError("This device does not support stereo loopback. Select a stereo output device.")
        try:
            audio.is_format_supported(SAMPLE_RATE, input_device=device["index"],
                                      input_channels=CHANNELS, input_format=pyaudio.paInt16)
        except ValueError as exc:
            raise RuntimeError("Loopback must support 48 kHz stereo PCM. Set the Windows output format to 48 kHz, or select another output device.") from exc

        print(f"Capturing output: {device['name']} (48 kHz stereo). Ctrl+C stops.")
        # The callback never waits on the network. At most 40 ms is queued; when
        # the sender stalls, keep fresh audio rather than replaying an old backlog.
        chunks: queue.Queue[bytes] = queue.Queue(maxsize=8)
        dropped = 0

        def callback(data, frame_count, time_info, status):
            nonlocal dropped
            if len(data) > PAYLOAD_BYTES * 16:
                dropped += 1
                return (None, pyaudio.paContinue)
            try:
                chunks.put_nowait(data)
            except queue.Full:
                try:
                    chunks.get_nowait()
                except queue.Empty:
                    pass
                dropped += 1
                try:
                    chunks.put_nowait(data)
                except queue.Full:
                    pass
            return (None, pyaudio.paContinue)

        started = time.monotonic()
        sequence = 0
        sent = 0
        pending = b""
        deadline = started
        assert sock is not None
        try:
            with audio.open(format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE,
                            input=True, input_device_index=device["index"],
                            frames_per_buffer=FRAMES, stream_callback=callback):
                while duration is None or time.monotonic() - started < duration:
                    try:
                        chunk = chunks.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    pending += chunk
                    while len(pending) >= PAYLOAD_BYTES:
                        if duration is not None and time.monotonic() - started >= duration:
                            return sent
                        pcm, pending = pending[:PAYLOAD_BYTES], pending[PAYLOAD_BYTES:]
                        delay = deadline - time.monotonic()
                        if delay > 0:
                            time.sleep(delay)
                        send_packet(sock, encode_packet(pcm, stream_id, sequence))
                        sent += 1
                        sequence = (sequence + 1) & 0xFFFFFFFF
                        deadline += INTERVAL
                        if time.monotonic() - deadline > INTERVAL:
                            deadline = time.monotonic() + INTERVAL
        finally:
            if dropped:
                print(f"Capture queue discarded {dropped} stale chunks to bound latency.", file=sys.stderr)
        return sent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", help="Phone IPv4 address or hostname, shown by LAN Audio")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp",
                        help="TCP reliability by default; UDP is available for experimentation")
    parser.add_argument("--tone", action="store_true", help="Send a quiet test tone; do not capture system audio")
    parser.add_argument("--duration", type=float, help="Stop after this many seconds; otherwise run until Ctrl+C")
    parser.add_argument("--list-devices", action="store_true", help="List Windows output loopback devices, without recording")
    parser.add_argument("--device", type=int, help="WASAPI loopback device index from --list-devices")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be 1 through 65535")
    if args.duration is not None and (not math.isfinite(args.duration) or args.duration <= 0):
        parser.error("--duration must be a positive finite number")
    if not args.list_devices and not args.host:
        parser.error("--host is required unless using --list-devices")
    if args.list_devices and args.tone:
        parser.error("--list-devices and --tone cannot be combined")
    try:
        if args.list_devices:
            return capture_windows(None, 0, None, None, True)
        stream_id = secrets.randbits(32)
        socket_type = socket.SOCK_STREAM if args.transport == "tcp" else socket.SOCK_DGRAM
        with socket.socket(socket.AF_INET, socket_type) as sock:
            sock.settimeout(3.0)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32_768)
            if args.transport == "tcp":
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.connect((args.host, args.port))
            sock.settimeout(1.0)
            print(f"Sending {'test tone' if args.tone else 'system output'} over {args.transport.upper()} to {sock.getpeername()[0]}:{args.port}.")
            sent = (send_tone(sock, stream_id, args.duration) if args.tone else
                    capture_windows(sock, stream_id, args.duration, args.device, False))
            print(f"Stopped after {sent} packets ({sent * INTERVAL:.2f} seconds of audio).")
        return 0
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
