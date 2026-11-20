package io.github.neuronsarealsocool.lanaudio;
import org.junit.Test;
import static org.junit.Assert.*;
import java.nio.*;
public class AudioBufferTest {
    private byte[] bytes(int stream,int seq){ByteBuffer b=ByteBuffer.allocate(980).order(ByteOrder.BIG_ENDIAN);b.putInt(0x4c4e4131).putInt(stream).putInt(seq).putShort((short)48000).putShort((short)2).putInt(240);b.put((byte)seq);return b.array();}
    private AudioPacket packet(int stream,int seq){return AudioPacket.parse(bytes(stream,seq),980);}
    @Test public void rejectsMalformedPackets(){byte[] b=bytes(1,0);assertNotNull(AudioPacket.parse(b,980));assertNull(AudioPacket.parse(b,979));assertNull(AudioPacket.parse(b,2048));b[0]=0;assertNull(AudioPacket.parse(b,980));b=bytes(1,0);b[13]=1;assertNull(AudioPacket.parse(b,980));b=bytes(1,0);b[19]=0;assertNull(AudioPacket.parse(b,980));}
    @Test public void preRollReordersAndConceals(){JitterBuffer j=new JitterBuffer();j.offer(packet(1,0),0);j.offer(packet(1,2),10);j.offer(packet(1,1),15);assertNull(j.next(119));assertEquals(0,j.next(120)[0]);assertEquals(1,j.next(125)[0]);assertEquals(2,j.next(130)[0]);assertArrayEquals(new byte[960],j.next(135));assertEquals(1,j.concealed);assertFalse(j.offer(packet(1,0),80));}
    @Test public void wrapsAndRecoversAfterIdle(){JitterBuffer j=new JitterBuffer();j.offer(packet(1,-1),0);j.offer(packet(1,0),5);assertEquals((byte)255,j.next(120)[0]);assertEquals(0,j.next(125)[0]);assertNull(j.next(500));assertTrue(j.offer(packet(2,0),600));assertEquals(0,j.next(720)[0]);}
    @Test public void boundedMemoryAndStreamPinning(){JitterBuffer j=new JitterBuffer();j.offer(packet(1,0),0);assertFalse(j.offer(packet(2,0),1));for(int i=1;i<10000;i++)j.offer(packet(1,i),i);assertTrue(j.size()<=101);assertTrue(j.resyncs>0);}
    @Test public void recoversFromSenderStallWithoutLongSilence(){JitterBuffer j=new JitterBuffer();j.offer(packet(1,0),0);assertNotNull(j.next(120));for(int i=0;i<6;i++)assertNotNull(j.next(125+i*5));assertTrue(j.offer(packet(1,1),155));assertNull(j.next(160));assertEquals(1,j.next(275)[0]);assertEquals(1,j.resyncs);}
}
