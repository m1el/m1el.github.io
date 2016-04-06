bg_h=950
fg_h=814

fmt = r'''iconvert \
    opening_bg.jpg -crop 800x450+240+{y1} \
    \( timeline.png -geometry +0{s2}{y2} \) -composite \
    \( timeline.png -geometry +0{s3}{y3} \) -composite \
    \( timeline.png -geometry +0{s4}{y4} \) -composite \
    \( hitagi_{hitagi}.png -gravity center -resize 50% \) -composite \
    loop/out_{o:03d}.png'''

for i in range(60):
  y1 = 200+(i*bg_h/60/3)
  y2 = -i*fg_h/60
  s2 = '' if y2 < 0 else '+'
  y3 = y2+fg_h
  s3 = '' if y3 < 0 else '+'
  y4 = y3+fg_h
  s4 = '' if y4 < 0 else '+'
  print(fmt.format(y1=y1,y2=y2,y3=y3,y4=y4,
                   s2=s2,s3=s3,s4=s4,o=i,
                   hitagi=(i//2)%6))
