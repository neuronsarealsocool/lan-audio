"""LAN Audio Windows sender. GUI and hidden worker share one portable executable."""
import argparse
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import time

from preferences import load_settings, save_settings, set_startup, settings_dir, startup_enabled

TITLE='LAN Audio — Windows Sender'
IPC_PORT=48101

def worker_command(host,transport,tone,logfile):
    command=[sys.executable]
    if not getattr(sys,'frozen',False):command.append(str(Path(__file__).resolve()))
    command+=['--worker','--log-file',str(logfile),'--host',host,'--transport',transport]
    if tone:command+=['--tone','--duration','5']
    return command

def valid_host(host):
    # No shell is used. Hostnames and IPv4 addresses are accepted; a port is separate.
    return bool(host) and len(host)<=253 and not any(c.isspace() for c in host) and ':' not in host and not host.startswith('-')

def run_worker():
    index=sys.argv.index('--log-file');log=Path(sys.argv[index+1]);log.parent.mkdir(parents=True,exist_ok=True)
    sys.stdout=log.open('w',encoding='utf-8',buffering=1);sys.stderr=sys.stdout
    import sender
    return sender.main(sys.argv[index+2:])

class SenderApp:
    def __init__(self,root,background=False):
        import tkinter as tk
        from tkinter import ttk
        self.root=root;self.events=queue.Queue();self.process=None;self.desired=False;self.retry_at=None;self.tone=False;self.closing=False;self.log_offset=0
        self.tray=None;self.logfile=settings_dir()/'sender.log';self.settings=load_settings()
        root.title(TITLE);root.geometry('560x650');root.minsize(520,620)
        root.configure(background='#F4F7F8')
        try:root.iconbitmap(str(Path(__file__).with_name('assets')/'lan-audio.ico'))
        except tk.TclError:pass
        style=ttk.Style();style.theme_use('clam')
        style.configure('.',font=('Segoe UI',10),background='#F4F7F8',foreground='#153341')
        style.configure('Title.TLabel',font=('Segoe UI Semibold',25))
        style.configure('Status.TLabel',font=('Segoe UI Semibold',12))
        style.configure('TButton',padding=(14,9))
        style.configure('Accent.TButton',background='#153E4D',foreground='white',font=('Segoe UI Semibold',11))
        style.map('Accent.TButton',background=[('active','#245E70')])
        frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
        title=ttk.Frame(frame);title.pack(fill='x')
        self.image=tk.PhotoImage(file=str(Path(__file__).with_name('assets')/'lan-audio.png')).subsample(8)
        ttk.Label(title,image=self.image).pack(side='left',padx=(0,14))
        titles=ttk.Frame(title);titles.pack(side='left')
        ttk.Label(titles,text='LAN Audio',style='Title.TLabel').pack(anchor='w')
        ttk.Label(titles,text='Windows sound → your phone').pack(anchor='w')
        ttk.Separator(frame).pack(fill='x',pady=18)
        ttk.Label(frame,text='Phone address').pack(anchor='w')
        self.host=tk.StringVar(value=self.settings.get('host',''))
        self.address=ttk.Entry(frame,textvariable=self.host,font=('Segoe UI',13));self.address.pack(fill='x',pady=(6,4))
        ttk.Label(frame,text='Shown in the Android app. Start the speaker there first.').pack(anchor='w')
        options=ttk.Frame(frame);options.pack(fill='x',pady=(14,14))
        ttk.Label(options,text='Connection').pack(side='left')
        self.transport=tk.StringVar(value=self.settings.get('transport','tcp'))
        self.connection=ttk.Combobox(options,textvariable=self.transport,values=('tcp','udp'),state='readonly',width=8);self.connection.pack(side='left',padx=12)
        ttk.Label(options,text='TCP recommended').pack(side='left')
        self.status=tk.StringVar(value='Stopped · ready when you are')
        ttk.Label(frame,textvariable=self.status,style='Status.TLabel',wraplength=490).pack(anchor='w',pady=(0,12))
        actions=ttk.Frame(frame);actions.pack(fill='x')
        self.start_button=ttk.Button(actions,text='Start audio',style='Accent.TButton',command=self.start);self.start_button.pack(side='left')
        self.stop_button=ttk.Button(actions,text='Stop',command=self.stop,state='disabled');self.stop_button.pack(side='left',padx=8)
        self.test_button=ttk.Button(actions,text='Test tone · 5 sec',command=lambda:self.start(True));self.test_button.pack(side='left')
        self.at_login=tk.BooleanVar(value=startup_enabled())
        self.resume=tk.BooleanVar(value=bool(self.settings.get('resume',False)))
        self.reconnect=tk.BooleanVar(value=bool(self.settings.get('reconnect',True)))
        ttk.Checkbutton(frame,text='Open in the tray at Windows sign-in',variable=self.at_login,command=self.change_startup).pack(anchor='w',pady=(18,3))
        ttk.Checkbutton(frame,text='Start audio automatically when the app opens',variable=self.resume,command=self.save).pack(anchor='w',pady=3)
        ttk.Checkbutton(frame,text='Reconnect while Start audio is active',variable=self.reconnect,command=self.save).pack(anchor='w',pady=3)
        ttk.Label(frame,text='Start sends your system output to this phone. Test tone sends only a generated sound. Stop ends capture. Closing the window keeps it in the tray; use Quit to exit.',wraplength=490).pack(anchor='w',pady=(12,8))
        self.detail=tk.StringVar(value='Enter the phone address to begin.')
        ttk.Label(frame,textvariable=self.detail,wraplength=490).pack(anchor='w')
        footer=ttk.Frame(frame);footer.pack(side='bottom',fill='x',pady=(10,0))
        ttk.Button(footer,text='Hide to tray',command=self.hide).pack(side='left')
        ttk.Button(footer,text='Quit',command=self.quit).pack(side='right')
        root.protocol('WM_DELETE_WINDOW',self.hide)
        self.setup_tray();root.after(150,self.poll)
        if background and self.tray:root.withdraw()
        if self.resume.get() and valid_host(self.host.get().strip()):root.after(500,self.start)

    def save(self):
        from tkinter import messagebox
        try:save_settings({'host':self.host.get().strip(),'transport':self.transport.get(),'resume':self.resume.get(),'reconnect':self.reconnect.get()})
        except OSError as e:messagebox.showerror('Settings could not be saved',str(e),parent=self.root)

    def change_startup(self):
        from tkinter import messagebox
        try:set_startup(self.at_login.get());self.save()
        except OSError as e:self.at_login.set(startup_enabled());messagebox.showerror('Windows startup',str(e),parent=self.root)

    def setup_tray(self):
        try:
            import pystray
            from PIL import Image
            def event(name):return lambda icon,item:self.events.put(('action',name))
            self.tray=pystray.Icon('LANAudio',Image.open(Path(__file__).with_name('assets')/'lan-audio.png'),'LAN Audio · stopped',
                pystray.Menu(pystray.MenuItem('Open LAN Audio',event('show'),default=True),pystray.MenuItem('Stop audio',event('stop')),pystray.MenuItem('Quit',event('quit'))))
            self.tray.run_detached()
        except Exception as e:self.tray=None;self.detail.set('Tray unavailable. Closing this window will quit. '+str(e))

    def show(self):self.root.deiconify();self.root.lift();self.root.focus_force()
    def hide(self):
        if self.tray:self.save();self.root.withdraw()
        else:self.quit()

    def start(self,tone=False):
        from tkinter import messagebox
        if self.process is not None or self.desired:return
        host=self.host.get().strip()
        if not valid_host(host):messagebox.showerror('Phone address','Enter the phone IPv4 address or hostname, without a port.',parent=self.root);return
        self.save();self.tone=tone;self.desired=not tone;self.retry_at=None;self.spawn()

    def spawn(self):
        self.logfile.parent.mkdir(parents=True,exist_ok=True);self.logfile.write_text('',encoding='utf-8');self.log_offset=0
        command=worker_command(self.host.get().strip(),self.transport.get(),self.tone,self.logfile)
        try:
            self.process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except OSError as e:self.desired=False;self.status.set('Could not start audio');self.detail.set(str(e));return
        self.status.set('Connecting…');self.detail.set('Start the speaker in the Android app.');self.set_busy(True)

    def set_busy(self,busy):
        self.start_button.configure(state='disabled' if busy else 'normal');self.test_button.configure(state='disabled' if busy else 'normal')
        self.stop_button.configure(state='normal' if busy else 'disabled');self.address.configure(state='disabled' if busy else 'normal');self.connection.configure(state='disabled' if busy else 'readonly')
        if self.tray:self.tray.title='LAN Audio · '+('audio active' if busy else 'stopped')

    def stop(self):
        self.desired=False;self.retry_at=None
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=2)
            self.process=None
        self.status.set('Stopped · capture is off');self.detail.set('You can stop the phone speaker too when finished.');self.set_busy(False)

    def poll(self):
        while not self.events.empty():
            kind,action=self.events.get_nowait()
            if kind=='action':
                if action=='quit':self.quit();return
                if action=='show':self.show()
                if action=='stop':self.stop()
        if self.process is not None:
            try:
                with self.logfile.open(encoding='utf-8',errors='replace') as log:
                    log.seek(self.log_offset);text=log.read();self.log_offset=log.tell()
                for line in text.splitlines():
                    if line:self.detail.set(line[-500:])
                    if line.startswith('Capturing output:'):self.status.set('Sending system audio')
                    elif line.startswith('Sending test tone'):self.status.set('Playing test tone · 5 seconds')
            except OSError:pass
            result=self.process.poll()
            if result is not None:
                self.process=None
                if self.desired and self.reconnect.get():self.retry_at=time.monotonic()+3;self.status.set('Disconnected · retrying in 3 seconds')
                else:self.desired=False;self.status.set('Test tone finished' if self.tone and result==0 else 'Stopped' if result==0 else 'Could not connect · check phone address and speaker');self.set_busy(False)
        if self.retry_at is not None and time.monotonic()>=self.retry_at:self.retry_at=None;self.spawn()
        if not self.closing:self.root.after(200,self.poll)

    def quit(self):
        self.closing=True;self.save();self.stop()
        if self.tray:self.tray.stop()
        self.root.destroy()

def main():
    if '--worker' in sys.argv:return run_worker()
    parser=argparse.ArgumentParser();parser.add_argument('--background',action='store_true');args=parser.parse_args()
    import tkinter as tk
    # One GUI per Windows user session. Additional launches restore the existing GUI.
    import ctypes
    mutex=None
    if sys.platform=='win32':
        ctypes.windll.kernel32.CreateMutexW.restype=ctypes.c_void_p
        mutex=ctypes.windll.kernel32.CreateMutexW(None,False,'Local\\LANAudioSenderGUI')
        if ctypes.windll.kernel32.GetLastError()==183:
            handle=ctypes.windll.user32.FindWindowW(None,TITLE)
            if handle:ctypes.windll.user32.ShowWindow(handle,9);ctypes.windll.user32.SetForegroundWindow(handle)
            return 0
    root=tk.Tk();app=SenderApp(root,args.background);root.mainloop()
    if mutex:ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))
    return 0

if __name__=='__main__':raise SystemExit(main())
