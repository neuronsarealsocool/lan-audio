import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import preferences
from protocol import decode_packet, PACKET_BYTES
from gui import valid_host, worker_command

class PreferencesTests(unittest.TestCase):
    def test_corrupt_preferences_recover_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'LOCALAPPDATA':folder}):
            path=preferences.settings_dir();path.mkdir()
            (path/'settings.json').write_text('{broken')
            self.assertEqual(preferences.load_settings(),{})
            data={'host':'speaker.local','resume':False,'reconnect':True,'transport':'tcp'}
            preferences.save_settings(data)
            self.assertEqual(preferences.load_settings(),data)
            self.assertFalse((path/'settings.tmp').exists())
    def test_startup_and_worker_quote_executable_path_with_spaces(self):
        with patch.object(preferences.sys,'frozen',True,create=True),patch.object(preferences.sys,'executable',r'C:\Apps\LAN Audio\LAN Audio.exe'):
            self.assertEqual(preferences.startup_command(),'"C:\\Apps\\LAN Audio\\LAN Audio.exe" --background')
            command=worker_command('speaker.local','tcp',False,Path('sender.log'))
            self.assertEqual(command[0],r'C:\Apps\LAN Audio\LAN Audio.exe')
            self.assertIn('--worker',command)
            self.assertEqual(command[-4:],['--host','speaker.local','--transport','tcp'])
    def test_host_field_rejects_blank_or_embedded_port(self):
        for host in ('','a b','192.168.1.2:48100','--tone'):
            self.assertFalse(valid_host(host))
        self.assertTrue(valid_host('speaker.local'));self.assertTrue(valid_host('192.168.1.2'))

class PackagedWorkerTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('LAN_AUDIO_EXE'),'set LAN_AUDIO_EXE for packaged integration test')
    def test_windowless_executable_worker_sends_valid_tone(self):
        with tempfile.TemporaryDirectory() as folder,socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(15)
            log=Path(folder)/'worker.log'
            process=subprocess.Popen([os.environ['LAN_AUDIO_EXE'],'--worker','--log-file',str(log),'--host','127.0.0.1','--port',str(listener.getsockname()[1]),'--tone','--duration','0.2'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                conn,_=listener.accept();data=b''
                with conn:
                    conn.settimeout(5)
                    while chunk:=conn.recv(4096):data+=chunk
                self.assertEqual(process.wait(10),0)
                self.assertEqual(len(data)%PACKET_BYTES,0);self.assertGreater(len(data)//PACKET_BYTES,10)
                sequences=[decode_packet(data[i:i+PACKET_BYTES])[1] for i in range(0,len(data),PACKET_BYTES)]
                self.assertEqual(sequences,list(range(len(sequences))))
                self.assertIn('over TCP',log.read_text())
            finally:
                if process.poll() is None:process.kill();process.wait()

if __name__=='__main__':unittest.main()
