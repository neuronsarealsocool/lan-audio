# LAN Audio wire protocol v1

An independent protocol for this project. Compatibility with the proprietary
WiFiAudio desktop helper is not claimed. Each framed block contains 5 ms of audio:
a 20-byte network-order header followed by 960 bytes of PCM.
Default transport: **TCP**, destination port **48100**. UDP on port 48100 is an
optional experimental transport. The reference sender uses unicast IPv4.

| Offset | Bytes | Field | Value |
| --- | --- | --- | --- |
| 0 | 4 | Magic | ASCII `LNA1` |
| 4 | 4 | Stream ID | Random unsigned 32-bit integer per sender invocation |
| 8 | 4 | Sequence | Unsigned 32-bit packet number; begins at 0, wraps modulo 2^32 |
| 12 | 2 | Sample rate | Unsigned 48000 |
| 14 | 2 | Channels | Unsigned 2 |
| 16 | 4 | Frame count | Unsigned 240 |
| 20 | 960 | Audio | Interleaved left/right signed 16-bit **little-endian** PCM |

Header integers are **big-endian**, equivalent to Python `struct.Struct('!4sIIHHI')`.
A PCM frame is one sample per channel. Each complete framed block must be
**980 bytes**. There is no padding, timestamp, compression, or negotiation.
Receivers reject blocks with a different size, magic, sample rate, channel count,
or frame count before handing audio to the playback queue.

For **TCP**, the client opens one connection and writes consecutive 980-byte
blocks. There is no length prefix or handshake beyond each block's fixed header.
The receiver must accumulate exactly 980 bytes per block: a socket read may
return a fraction of a block or contain multiple blocks. EOF with a partial block
is a truncated stream; discard the partial block. Set `TCP_NODELAY` to avoid
Nagle coalescing. The sender allows three seconds to connect and one second per
send before failing. TCP handles retransmission and ordered delivery, trading
potential latency for reliability on lossy Wi-Fi. A stalled stream should be
closed rather than accumulating unbounded old audio. There is no automatic
reconnect in the reference sender.

For **UDP**, each datagram contains exactly one 980-byte block. There is no
application retransmission; loss and out-of-order delivery are expected.

Known vector: stream ID `0x01020304`, sequence `0xA0B0C0D0`:

```text
4c 4e 41 31 01 02 03 04 a0 b0 c0 d0 bb 80 00 02 00 00 00 f0
```

PCM sample pair left=-1234, right=5678 encodes as `2e fb 2e 16`.

Send 200 blocks/second at roughly 5 ms intervals. When scheduling is delayed,
discard stale audio or resume from the current deadline, rather than sending a
large catch-up burst. A random stream ID distinguishes sender restarts. Sequence
numbers permit loss, duplicate, and stale-block detection with modulo arithmetic.
The receiver owns its bounded jitter buffer and loss-concealment policy.

This protocol has no authentication, integrity protection, encryption, or pairing.
Only run it on a trusted LAN. The receiver should pin an active source endpoint
while a session is live and release that binding after an idle timeout; this is
collision avoidance, not a security boundary. No internet port forwarding.
