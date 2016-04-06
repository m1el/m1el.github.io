python3 mk.py | sh
ffmpeg -framerate 30 -i loop/out_%03d.png -c:v libvpx -crf 15 -b:v 1M hitagi-drop.webm
