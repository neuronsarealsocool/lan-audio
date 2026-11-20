import socket
import struct
import subprocess
import sys
import time
import unittest
from pathlib import Path

from protocol import (CHANNELS, FRAMES, HEADER, MAGIC, PACKET_BYTES, PAYLOAD_BYTES,
                      SAMPLE_RATE, decode_packet, encode_packet)
from sender import tone_chunk


class ProtocolTests(unittest.TestCase):
    def test_known_network_header_and_little_endian_samples(self):
        pcm = struct.pack("<hh", -1234, 5678) * FRAMES
        packet = encode_packet(pcm, 0x01020304, 0xA0B0C0D0)
        self.assertEqual(packet[:20], bytes.fromhex("4c4e413101020304a0b0c0d0bb800002000000f0"))
        self.assertEqual(packet[20:24], bytes.fromhex("2efb2e16"))
        self.assertEqual(decode_packet(packet), (0x01020304, 0xA0B0C0D0, pcm))

    def test_reject_truncated_extended_and_unsupported_packets(self):
        valid = encode_packet(bytes(PAYLOAD_BYTES), 1, 2)
        candidates = [valid[:-1], valid + b"\0"]
        for fields in ((b"NOPE", 1, 2, SAMPLE_RATE, CHANNELS, FRAMES),
                       (MAGIC, 1, 2, 44100, CHANNELS, FRAMES),
                       (MAGIC, 1, 2, SAMPLE_RATE, 1, FRAMES),
                       (MAGIC, 1, 2, SAMPLE_RATE, CHANNELS, FRAMES + 1)):
            candidates.append(HEADER.pack(*fields) + valid[20:])
        for candidate in candidates:
            with self.subTest(candidate=candidate[:20]), self.assertRaises(ValueError):
                decode_packet(candidate)

    def test_encoder_rejects_bad_pcm_and_identifiers(self):
        for bad in (b"", bytes(PAYLOAD_BYTES - 1), bytes(PAYLOAD_BYTES + 1)):
            with self.assertRaises(ValueError):
                encode_packet(bad, 0, 0)
        for bad in (-1, 2**32, 1.5, True):
            with self.assertRaises(ValueError):
                encode_packet(bytes(PAYLOAD_BYTES), bad, 0)
            with self.assertRaises(ValueError):
                encode_packet(bytes(PAYLOAD_BYTES), 0, bad)

    def test_tone_is_quiet_stereo_with_continuous_phase(self):
        samples = struct.unpack("<" + "h" * FRAMES * 2, tone_chunk(0))
        self.assertEqual(samples[0], 0)
        self.assertEqual(samples[::2], samples[1::2])
        self.assertLessEqual(max(abs(value) for value in samples), 2622)
        next_sample = struct.unpack_from("<h", tone_chunk(FRAMES))[0]
        self.assertEqual(next_sample, 2493)

    def test_cli_sends_paced_udp_without_capture_dependency(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            receiver.settimeout(2)
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("sender.py")),
                 "--host", "127.0.0.1", "--port", str(receiver.getsockname()[1]),
                 "--tone", "--duration", "0.15", "--transport", "udp"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            packets = []
            try:
                while True:
                    try:
                        packet, _ = receiver.recvfrom(2048)
                        packets.append(decode_packet(packet))
                        self.assertEqual(len(packet), PACKET_BYTES)
                    except socket.timeout:
                        break
                stdout, stderr = process.communicate(timeout=2)
                self.assertEqual(process.returncode, 0, (stdout, stderr))
                self.assertGreaterEqual(len(packets), 5)
                self.assertLessEqual(len(packets), 31)
                self.assertEqual(len({stream for stream, _, _ in packets}), 1)
                self.assertEqual([seq for _, seq, _ in packets], list(range(len(packets))))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_default_tcp_stream_reassembles_partial_reads_and_is_paced(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(3)
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("sender.py")),
                 "--host", "127.0.0.1", "--port", str(listener.getsockname()[1]),
                 "--tone", "--duration", "0.15"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            packets = []
            pending = b""
            times = []
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(2)
                    while True:
                        # Force packet boundaries across many small reads. TCP
                        # delivers bytes, not sender write/datagram boundaries.
                        chunk = connection.recv(73)
                        if not chunk:
                            break
                        pending += chunk
                        while len(pending) >= PACKET_BYTES:
                            packet, pending = pending[:PACKET_BYTES], pending[PACKET_BYTES:]
                            packets.append(decode_packet(packet))
                            times.append(time.monotonic())
                stdout, stderr = process.communicate(timeout=2)
                self.assertEqual(process.returncode, 0, (stdout, stderr))
                self.assertIn("over TCP", stdout)
                self.assertEqual(pending, b"")
                self.assertGreaterEqual(len(packets), 5)
                self.assertLessEqual(len(packets), 31)
                self.assertGreater(times[-1] - times[0], 0.08)
                self.assertEqual(len({stream for stream, _, _ in packets}), 1)
                self.assertEqual([seq for _, seq, _ in packets], list(range(len(packets))))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    unittest.main()
