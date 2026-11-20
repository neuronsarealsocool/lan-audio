package io.github.neuronsarealsocool.lanaudio;

import android.app.*;
import android.content.*;
import android.media.*;
import android.media.session.*;
import android.net.wifi.WifiManager;
import android.os.*;
import android.util.Log;
import java.net.*;

/** Audio belongs to this service; Activity recreation or dismissal never owns its lifetime. */
public final class PlaybackService extends Service {
    private static final String TAG="LanAudio", CHANNEL="speaker";
    public static volatile String status="Speaker stopped", statistics="";
    private volatile boolean running, focused;
    private volatile DatagramSocket socket;
    private volatile ServerSocket tcpServer;
    private volatile Socket tcpClient;
    private volatile AudioTrack activeTrack;
    private Thread receiver, tcpReceiver, player;
    private PowerManager.WakeLock cpu;
    private WifiManager.WifiLock wifi;
    private AudioManager audio;
    private AudioFocusRequest focusRequest;
    private MediaSession session;
    private final JitterBuffer buffer=new JitterBuffer();
    private String allowed="";
    private volatile long lastPacket;
    private volatile long written, invalid, underruns;
    private final AudioManager.OnAudioFocusChangeListener focusListener=change -> {
        focused=change==AudioManager.AUDIOFOCUS_GAIN;
        if(change==AudioManager.AUDIOFOCUS_LOSS) { status="Stopped: another app took audio focus"; stopSelf(); }
    };
    @Override public void onCreate() {
        super.onCreate(); audio=(AudioManager)getSystemService(AUDIO_SERVICE);
        if(Build.VERSION.SDK_INT>=26) {
            NotificationChannel c=new NotificationChannel(CHANNEL,"Wi-Fi speaker",NotificationManager.IMPORTANCE_LOW);
            c.setSound(null,null); ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(c);
        }
        session=new MediaSession(this,"LAN Audio");
        session.setCallback(new MediaSession.Callback() {
            @Override public void onStop(){stopSelf();}
            @Override public void onPause(){stopSelf();}
        });
        session.setFlags(MediaSession.FLAG_HANDLES_MEDIA_BUTTONS | MediaSession.FLAG_HANDLES_TRANSPORT_CONTROLS);
        session.setMetadata(new MediaMetadata.Builder().putString(MediaMetadata.METADATA_KEY_TITLE,"LAN Audio speaker").build());
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        if(intent!=null && "STOP".equals(intent.getAction())) { stopSelf();return START_NOT_STICKY; }
        if(running) return START_NOT_STICKY;
        // Do not re-arm after a system kill with a null intent. The user starts each session.
        if(intent==null){stopSelf();return START_NOT_STICKY;}
        allowed=intent.getStringExtra("sender");if(allowed==null)allowed="";
        try {
            startForeground(1,notification("Ready on TCP / UDP 48100"));
            cpu=((PowerManager)getSystemService(POWER_SERVICE)).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"LANAudio:receiver");
            cpu.setReferenceCounted(false);cpu.acquire(600_000L);
            WifiManager manager=(WifiManager)getApplicationContext().getSystemService(WIFI_SERVICE);
            if(manager!=null) { wifi=manager.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF,"LANAudio:network");wifi.setReferenceCounted(false);wifi.acquire(); }
            running=true;status="Starting speaker…";session.setActive(true);
            receiver=new Thread(this::receive,"lan-receive");tcpReceiver=new Thread(this::receiveTcp,"lan-tcp");player=new Thread(this::play,"lan-play");
            receiver.start();tcpReceiver.start();player.start();
        } catch(Exception e){fail(e);}
        // No hidden restarts or boot autostart. A foreground session stays alive across task dismissal.
        return START_NOT_STICKY;
    }
    private Notification notification(String text) {
        PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,PlaybackService.class).setAction("STOP"),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder b=Build.VERSION.SDK_INT>=26?new Notification.Builder(this,CHANNEL):new Notification.Builder(this);
        return b.setContentTitle("LAN Audio speaker").setContentText(text).setSmallIcon(R.drawable.ic_speaker)
            .setContentIntent(open).setOngoing(true).setVisibility(Notification.VISIBILITY_PUBLIC)
            .addAction(new Notification.Action.Builder(android.R.drawable.ic_media_pause,"Stop",stop).build())
            .setStyle(new Notification.MediaStyle().setMediaSession(session.getSessionToken()).setShowActionsInCompactView(0)).build();
    }
    private void receive() {
        try(DatagramSocket s=new DatagramSocket(null)) {
            s.setReuseAddress(true);s.setReceiveBufferSize(65536);s.bind(new InetSocketAddress(48100));s.setSoTimeout(1000);socket=s;
            status="Ready · TCP / UDP 48100";Log.i(TAG,"READY port=48100");
            byte[] bytes=new byte[2048];DatagramPacket datagram=new DatagramPacket(bytes,bytes.length);
            SocketAddress peer=null;long peerAt=0,renewAt=SystemClock.elapsedRealtime()+300_000L;
            while(running) {
                if(SystemClock.elapsedRealtime()>=renewAt){cpu.acquire(600_000L);renewAt=SystemClock.elapsedRealtime()+300_000L;}
                try {
                    datagram.setLength(bytes.length);s.receive(datagram);
                    if(tcpClient!=null)continue;
                    long now=SystemClock.elapsedRealtime();
                    if(!allowed.isEmpty() && !datagram.getAddress().getHostAddress().equals(allowed))continue;
                    if(peer!=null && !peer.equals(datagram.getSocketAddress()) && now-peerAt<2000)continue;
                    AudioPacket packet=AudioPacket.parse(bytes,datagram.getLength());if(packet==null){invalid++;continue;}
                    if(buffer.offer(packet,now)) {peer=datagram.getSocketAddress();peerAt=now;lastPacket=now;}
                } catch(SocketTimeoutException ignored) { }
            }
        } catch(Exception e) { if(running)fail(e); }
        finally { socket=null; }
    }
    private void receiveTcp() {
        try(ServerSocket server=new ServerSocket()) {
            server.setReuseAddress(true);server.bind(new InetSocketAddress(48100),1);server.setSoTimeout(1000);tcpServer=server;
            while(running) {
                try(Socket client=server.accept()) {
                    if(!allowed.isEmpty() && !client.getInetAddress().getHostAddress().equals(allowed))continue;
                    client.setTcpNoDelay(true);client.setReceiveBufferSize(32768);client.setSoTimeout(1000);tcpClient=client;
                    byte[] bytes=new byte[AudioPacket.HEADER+AudioPacket.PAYLOAD];int offset=0;
                    java.io.InputStream input=client.getInputStream();
                    Log.i(TAG,"TCP_CONNECTED");
                    while(running) {
                        try {
                            int count=input.read(bytes,offset,bytes.length-offset);if(count<0)break;offset+=count;
                            if(offset<bytes.length)continue;
                            AudioPacket packet=AudioPacket.parse(bytes,bytes.length);offset=0;
                            if(packet==null){invalid++;break;}
                            long now=SystemClock.elapsedRealtime();if(buffer.offer(packet,now))lastPacket=now;
                        }catch(SocketTimeoutException ignored) { }
                    }
                }catch(SocketTimeoutException ignored) { }
                catch(java.io.IOException e){if(running)Log.i(TAG,"TCP sender disconnected: "+e.getClass().getSimpleName());}
                finally{tcpClient=null;}
            }
        }catch(Exception e){if(running)fail(e);}
        finally{tcpServer=null;}
    }
    private boolean requestFocus() {
        int result;
        if(Build.VERSION.SDK_INT>=26) {
            focusRequest=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(attributes()).setOnAudioFocusChangeListener(focusListener,new Handler(getMainLooper())).build();
            result=audio.requestAudioFocus(focusRequest);
        }else result=audio.requestAudioFocus(focusListener,AudioManager.STREAM_MUSIC,AudioManager.AUDIOFOCUS_GAIN);
        focused=result==AudioManager.AUDIOFOCUS_REQUEST_GRANTED;return focused;
    }
    private void abandonFocus(){focused=false;if(Build.VERSION.SDK_INT>=26 && focusRequest!=null)audio.abandonAudioFocusRequest(focusRequest);else audio.abandonAudioFocus(focusListener);}
    private AudioAttributes attributes(){return new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build();}
    private void play() {
        android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_AUDIO);
        AudioTrack track=null;boolean playing=false;long lastReport=0, deadline=0;
        try {
            int min=AudioTrack.getMinBufferSize(AudioPacket.RATE,AudioFormat.CHANNEL_OUT_STEREO,AudioFormat.ENCODING_PCM_16BIT);
            if(min<=0)throw new IllegalStateException("Unsupported audio output: "+min);
            track=new AudioTrack.Builder().setAudioAttributes(attributes()).setAudioFormat(new AudioFormat.Builder()
                .setSampleRate(AudioPacket.RATE).setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                .setBufferSizeInBytes(Math.max(min,AudioPacket.PAYLOAD*12)).setTransferMode(AudioTrack.MODE_STREAM).build();
            if(track.getState()!=AudioTrack.STATE_INITIALIZED)throw new IllegalStateException("Audio output initialization failed");
            activeTrack=track;
            while(running) {
                long now=SystemClock.elapsedRealtime();byte[] pcm=buffer.next(now);
                if(pcm==null) {
                    if(playing && now-lastPacket>300){track.pause();track.flush();playing=false;abandonFocus();update("Ready · waiting for sender",false);}
                    buffer.awaitInput();
                }else {
                    if(!playing) {
                        if(!requestFocus()){status="Audio focus unavailable · retrying";Thread.sleep(500);continue;}
                        // Keep 30ms in the device queue so small scheduler delays
                        // do not turn each 5ms application block into an output underrun.
                        byte[] prime=new byte[AudioPacket.PAYLOAD*6];
                        int primed=track.write(prime,0,prime.length,AudioTrack.WRITE_NON_BLOCKING);
                        if(primed<0)throw new IllegalStateException("Audio output priming failed: "+primed);
                        track.play();playing=true;deadline=System.nanoTime();update("Playing · screen can turn off",true);
                    }
                    track.setVolume(focused?1f:0f);
                    int offset=0;
                    while(running && offset<pcm.length) {
                        int count=track.write(pcm,offset,pcm.length-offset,AudioTrack.WRITE_BLOCKING);
                        if(count<0)throw new IllegalStateException("AudioTrack write failed: "+count);
                        if(count==0){Thread.sleep(1);continue;}offset+=count;
                    }
                    written+=offset/4;
                    // AudioTrack accepts an initial burst while filling its own buffer.
                    // Pace playout explicitly so that burst cannot consume future sequence slots.
                    deadline+=5_000_000L;
                    long remaining=deadline-System.nanoTime();
                    if(remaining>0)java.util.concurrent.locks.LockSupport.parkNanos(remaining);
                    else if(remaining < -50_000_000L)deadline=System.nanoTime();
                }
                if(now-lastReport>=5000) {
                    underruns=Build.VERSION.SDK_INT>=24?track.getUnderrunCount():0;statistics=buffer.stats()+"\nFrames " + written + " · output underruns " + underruns + " · invalid " + invalid;
                    Log.i(TAG,"HEALTH frames="+written+" "+buffer.health()+" underruns="+underruns+" invalid="+invalid);
                    lastReport=now;
                }
            }
        }catch(InterruptedException ignored) { }
        catch(Exception e){if(running)fail(e);}
        finally{activeTrack=null;if(track!=null){try{track.pause();track.flush();}catch(Exception ignored){}track.release();}abandonFocus();}
    }
    private void update(String text,boolean playing) {
        if(!running)return;
        status=text;session.setPlaybackState(new PlaybackState.Builder()
            .setActions(PlaybackState.ACTION_STOP|PlaybackState.ACTION_PAUSE)
            .setState(playing?PlaybackState.STATE_PLAYING:PlaybackState.STATE_PAUSED,PlaybackState.PLAYBACK_POSITION_UNKNOWN,playing?1:0).build());
        ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(1,notification(text));
    }
    private void fail(Exception e){Log.e(TAG,"Speaker failed",e);status="Speaker error: "+e.getMessage();stopSelf();}
    @Override public void onDestroy() {
        running=false;DatagramSocket s=socket;if(s!=null)s.close();
        try{if(tcpServer!=null)tcpServer.close();}catch(java.io.IOException ignored){}
        try{if(tcpClient!=null)tcpClient.close();}catch(java.io.IOException ignored){}
        AudioTrack track=activeTrack;if(track!=null){try{track.pause();track.flush();}catch(IllegalStateException ignored){}}
        if(receiver!=null)receiver.interrupt();if(tcpReceiver!=null)tcpReceiver.interrupt();if(player!=null)player.interrupt();
        // A bounded join prevents a previous session from overlapping an immediate restart.
        try {if(receiver!=null)receiver.join(1000);if(tcpReceiver!=null)tcpReceiver.join(1000);if(player!=null)player.join(1000);}catch(InterruptedException e){Thread.currentThread().interrupt();}
        if(wifi!=null && wifi.isHeld())wifi.release();if(cpu!=null && cpu.isHeld())cpu.release();
        if(session!=null){session.setActive(false);session.release();}stopForeground(true);
        if(!status.startsWith("Speaker error") && !status.startsWith("Stopped:"))status="Speaker stopped";
        Log.i(TAG,"STOPPED frames="+written+" locks released");super.onDestroy();
    }
    @Override public IBinder onBind(Intent i){return null;}
}
