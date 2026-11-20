package io.github.neuronsarealsocool.lanaudio;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;

/** LNA1 framing. No Android dependencies so malformed traffic is unit testable. */
public final class AudioPacket {
    public static final int RATE = 48000, CHANNELS = 2, FRAMES = 240, PAYLOAD = 960, HEADER = 20;
    public final int stream, sequence;
    public final byte[] pcm;
    private AudioPacket(int stream, int sequence, byte[] pcm) { this.stream=stream; this.sequence=sequence; this.pcm=pcm; }
    public static AudioPacket parse(byte[] bytes, int length) {
        if (length != HEADER + PAYLOAD || length > bytes.length) return null;
        ByteBuffer b = ByteBuffer.wrap(bytes, 0, length).order(ByteOrder.BIG_ENDIAN);
        if (b.getInt() != 0x4c4e4131) return null;
        int stream=b.getInt(), sequence=b.getInt();
        if ((b.getShort() & 0xffff) != RATE || b.getShort() != CHANNELS || b.getInt() != FRAMES) return null;
        return new AudioPacket(stream, sequence, Arrays.copyOfRange(bytes, HEADER, length));
    }
}
