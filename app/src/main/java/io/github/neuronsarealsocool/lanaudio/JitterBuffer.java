package io.github.neuronsarealsocool.lanaudio;

import java.util.HashMap;
import java.util.Map;

/** Bounded 120ms pre-roll / 500ms window. Sequence subtraction also handles uint32 wrap. */
public final class JitterBuffer {
    private final Map<Integer,AudioPacket> packets = new HashMap<>();
    private boolean initialized, playing;
    private int stream, expected, emptyRun;
    private long lastInput, firstInput;
    public long received, concealed, late, resyncs;
    public synchronized boolean offer(AudioPacket p, long now) {
        if (!initialized || now-lastInput > 2000) reset(p, now);
        if (p.stream != stream) return false;
        int ahead = p.sequence-expected;
        if (ahead < 0) { late++; return false; }
        if (ahead > 100) { reset(p, now); resyncs++; }
        if (packets.containsKey(p.sequence)) return false;
        packets.put(p.sequence,p); lastInput=now; received++; notifyAll(); return true;
    }
    private void reset(AudioPacket p,long now) {
        packets.clear(); stream=p.stream; expected=p.sequence; emptyRun=0; initialized=true; playing=false; firstInput=now; lastInput=now;
    }
    public synchronized byte[] next(long now) {
        if (!initialized || now-lastInput > 250) { packets.clear(); playing=false; initialized=false; return null; }
        if (!playing) { if (now-firstInput < 120) return null; playing=true; }
        AudioPacket p=packets.remove(expected++);
        if (p == null) {
            concealed++;
            // After 30ms of missing audio, rebuffer around the next live packet
            // instead of repeatedly rejecting a sender that fell behind our clock.
            if(++emptyRun>=6){packets.clear();initialized=false;playing=false;resyncs++;}
            return new byte[AudioPacket.PAYLOAD];
        }
        emptyRun=0;
        return p.pcm;
    }
    public synchronized int size() { return packets.size(); }
    public synchronized String stats() { return "Packets " + received + " · gaps " + concealed + " · late " + late + " · queued " + packets.size(); }
    public synchronized String health() { return "received="+received+" gaps="+concealed+" late="+late+" queue="+packets.size()+" resyncs="+resyncs; }
    public synchronized void awaitInput() throws InterruptedException { if(packets.isEmpty())wait(100);else wait(5); }
}
