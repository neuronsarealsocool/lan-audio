"""LAN Audio v1 wire format; standard-library-only and shared by tests/tools."""

import struct

MAGIC = b"LNA1"
SAMPLE_RATE = 48_000
CHANNELS = 2
FRAMES = 240
SAMPLE_BYTES = 2
PORT = 48_100
HEADER = struct.Struct("!4sIIHHI")
PAYLOAD_BYTES = FRAMES * CHANNELS * SAMPLE_BYTES
PACKET_BYTES = HEADER.size + PAYLOAD_BYTES


def encode_packet(pcm: bytes, stream_id: int, sequence: int) -> bytes:
    """Encode exactly 5 ms of stereo signed-16-bit little-endian PCM."""
    if len(pcm) != PAYLOAD_BYTES:
        raise ValueError(f"PCM must contain exactly {PAYLOAD_BYTES} bytes")
    for name, value in (("stream_id", stream_id), ("sequence", sequence)):
        if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError(f"{name} must be an unsigned 32-bit integer")
    return HEADER.pack(MAGIC, stream_id, sequence, SAMPLE_RATE, CHANNELS, FRAMES) + pcm


def decode_packet(packet: bytes) -> tuple[int, int, bytes]:
    """Validate framing and return (stream id, sequence, PCM)."""
    if len(packet) != PACKET_BYTES:
        raise ValueError(f"Packet must contain exactly {PACKET_BYTES} bytes")
    magic, stream_id, sequence, rate, channels, frames = HEADER.unpack_from(packet)
    if (magic, rate, channels, frames) != (MAGIC, SAMPLE_RATE, CHANNELS, FRAMES):
        raise ValueError("Unsupported LAN Audio framing or audio format")
    return stream_id, sequence, packet[HEADER.size:]
