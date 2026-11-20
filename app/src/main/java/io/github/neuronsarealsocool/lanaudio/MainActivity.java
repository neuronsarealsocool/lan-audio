package io.github.neuronsarealsocool.lanaudio;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;
import java.net.*;
import java.util.*;

public final class MainActivity extends Activity {
    private final Handler handler=new Handler();
    private TextView status;
    private EditText sender;
    private final Runnable refresh=new Runnable() { public void run() {
        status.setText(PlaybackService.status + "\n\n" + PlaybackService.statistics); handler.postDelayed(this,1000);
    }};
    @Override public void onCreate(Bundle state) {
        super.onCreate(state); setVolumeControlStream(android.media.AudioManager.STREAM_MUSIC);
        LinearLayout column=new LinearLayout(this); column.setOrientation(LinearLayout.VERTICAL); column.setPadding(dp(24),dp(28),dp(24),dp(28));
        ScrollView scroll=new ScrollView(this); scroll.addView(column); setContentView(scroll);
        label(column,"LAN Audio",32); label(column,"Desktop sound. Screen off.",17);
        label(column,"Send to " + addresses() + ":48100",19);
        status=label(column,PlaybackService.status,18);
        label(column,"Optional: accept audio only from this PC’s IPv4 address",15);
        sender=new EditText(this); sender.setSingleLine(); sender.setHint("Any sender on your trusted LAN");
        sender.setInputType(android.text.InputType.TYPE_CLASS_PHONE);
        sender.setText(getPreferences(0).getString("sender","")); column.addView(sender);
        button(column,"Start speaker",v -> {
            String ip=sender.getText().toString().trim();
            if (!ip.isEmpty() && !validIp(ip)) { sender.setError("Enter a numeric IPv4 address"); return; }
            getPreferences(0).edit().putString("sender",ip).apply();
            if (Build.VERSION.SDK_INT>=33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},1);
            Intent i=new Intent(this,PlaybackService.class).putExtra("sender",ip);
            if(Build.VERSION.SDK_INT>=26) startForegroundService(i); else startService(i);
        });
        button(column,"Stop speaker",v -> stopService(new Intent(this,PlaybackService.class)));
        button(column,"Battery settings",v -> {
            try { startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)); }
            catch(ActivityNotFoundException e) { startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+getPackageName()))); }
        });
        label(column,"Start the speaker, then run the desktop sender. Playback continues when you go Home or turn the screen off. Stop here or from the notification.\n\nOn Samsung, also remove LAN Audio from Sleeping apps / Deep sleeping apps if necessary. Battery exemption is optional.\n\nUse a trusted private Wi-Fi network. This prototype receives unencrypted audio. It uses a CPU and Wi-Fi lock while the speaker is on, so stop it when finished.",16);
    }
    private boolean validIp(String text) {
        String[] parts=text.split("\\.",-1); if(parts.length!=4)return false;
        try {for(String part:parts) {if(!part.matches("[0-9]{1,3}") || Integer.parseInt(part)>255)return false;} return true;} catch(NumberFormatException e){return false;}
    }
    private int dp(int n){ return (int)(n*getResources().getDisplayMetrics().density); }
    private TextView label(LinearLayout parent,String text,int size){TextView t=new TextView(this);t.setText(text);t.setTextSize(size);t.setPadding(0,dp(8),0,dp(12));parent.addView(t);return t;}
    private void button(LinearLayout parent,String text,View.OnClickListener action){Button b=new Button(this);b.setText(text);b.setOnClickListener(action);parent.addView(b,new LinearLayout.LayoutParams(-1,dp(56)));}
    private String addresses(){
        try {ArrayList<String> result=new ArrayList<>();Enumeration<NetworkInterface> interfaces=NetworkInterface.getNetworkInterfaces();while(interfaces.hasMoreElements()){NetworkInterface n=interfaces.nextElement();if(!n.isUp()||n.isLoopback())continue;Enumeration<InetAddress> a=n.getInetAddresses();while(a.hasMoreElements()){InetAddress x=a.nextElement();if(x instanceof Inet4Address && !x.isLoopbackAddress())result.add(x.getHostAddress());}}return android.text.TextUtils.join(" / ",result);}catch(Exception e){return "your phone’s Wi-Fi IP";}
    }
    @Override public void onResume(){super.onResume();handler.post(refresh);}
    @Override public void onPause(){handler.removeCallbacks(refresh);super.onPause();}
}
