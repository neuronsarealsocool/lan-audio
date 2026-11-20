"""Render this project's code-native speaker mark for Android and Windows."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'desktop' / 'assets'
RES = ROOT / 'app' / 'src' / 'main' / 'res'
ASSETS.mkdir(parents=True, exist_ok=True)
NAVY, TEAL = '#102D3B', '#55E0C1'
SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108">
<rect width="108" height="108" rx="23" fill="#102D3B"/>
<path fill="#FFFFFF" d="M28 45H40L54 33V75L40 63H28Z"/>
<path fill="none" stroke="#55E0C1" stroke-width="5" stroke-linecap="round" d="M63.14 39.86A20 20 0 0 1 63.14 68.14M70.92 32.08A31 31 0 0 1 70.92 75.92"/>
</svg>'''
(ASSETS / 'lan-audio.svg').write_text(SVG)
size=1080
im=Image.new('RGBA',(size,size))
d=ImageDraw.Draw(im)
d.rounded_rectangle((0,0,1079,1079),radius=230,fill=NAVY)
d.polygon([(280,450),(400,450),(540,330),(540,750),(400,630),(280,630)],fill='white')
for r in (200,310):
    d.arc((490-r,540-r,490+r,540+r),-45,45,fill=TEAL,width=50)
    import math
    for angle in (-45,45):
        x=490+r*math.cos(math.radians(angle)); y=540+r*math.sin(math.radians(angle))
        d.ellipse((x-25,y-25,x+25,y+25),fill=TEAL)
icon=im.resize((512,512),Image.Resampling.LANCZOS)
icon.save(ASSETS/'lan-audio.png')
icon.save(ASSETS/'lan-audio.ico',sizes=[(n,n) for n in (16,20,24,32,40,48,64,128,256)])
for density,n in [('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)]:
    folder=RES/f'mipmap-{density}';folder.mkdir(parents=True,exist_ok=True)
    icon.resize((n,n),Image.Resampling.LANCZOS).save(folder/'ic_launcher.png')
