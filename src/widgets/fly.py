"""Procedural synthetic fly-inspired network, not measured anatomy or bot telemetry."""
import zlib


def fly_html():
    html = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;padding:22px 12px 18px;background:#030b17;color:#d9f5ff;font:12px sans-serif;text-align:center}h2{margin:0;color:#e8faff;font-size:19px;letter-spacing:4px;font-weight:600}p{margin:10px 0 0;color:#77abc5;font-size:11px;line-height:1.5}canvas{display:block;width:300px;height:320px;margin:8px auto}button{width:292px;padding:15px 8px;border:1px solid #2784aa;border-radius:14px;background:#0b3049;color:#dffaff;font:13px sans-serif}button:disabled{background:#071d30;color:#70a2b9}
</style></head><body><h2>Sensei FLY LAB</h2><p>Визуальная симуляция нейронной сети мухи</p><canvas id="net" width="300" height="320"></canvas><button id="start">Запустить симуляцию нейронов</button>
<script>
// Synthetic population model; displayed particles aggregate 20000 nodes, not anatomy.
var c=document.getElementById('net').getContext('2d'),N=20000,M=600,v=[],next=[],pts=[],projected=[],activity=[],seed=731,frame=0,timer=null;
function rnd(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;}
for(var i=0;i<N;i++){v.push(rnd()*.1);next.push(0);}
for(var i=0;i<M;i++){var k=i%300,a=k*2.399963,r=Math.sqrt((k+.5)/300),side=i<300?-1:1;
 pts.push({x:side*(48+Math.cos(a)*49*r),y:Math.sin(a)*91*r,phase:rnd()*6.28});projected.push({x:0,y:0});activity.push(0);}
function line(x,y,xx,yy,color,width){c.beginPath();c.moveTo(x,y);c.lineTo(xx,yy);c.strokeStyle=color;c.lineWidth=width;c.stroke();}
function ring(x,y,rx,ry,color){c.beginPath();for(var j=0;j<=24;j++){var a=j*6.283185/24,xx=x+Math.cos(a)*rx,yy=y+Math.sin(a)*ry;if(j===0)c.moveTo(xx,yy);else c.lineTo(xx,yy);}c.strokeStyle=color;c.lineWidth=1;c.stroke();}
function step(){for(var j=0;j<M;j++)activity[j]=0;
 for(var i=0;i<N;i++){var input=v[(i+1)%N]*.32+v[(i+137)%N]*(i%5===0?-.22:.28);next[i]=Math.max(0,Math.min(1,v[i]*.57+input));}
 for(var j=0;j<100;j++)next[Math.floor(rnd()*N)]=.5+rnd()*.5;
 for(var i=0;i<N;i++){v[i]=next[i];var bin=Math.floor(i*M/N);activity[bin]+=v[i];}
 for(var j=0;j<M;j++)activity[j]=Math.min(1,activity[j]*.3);}
function draw(moving){var t=frame*.14;c.fillStyle='#030b17';c.fillRect(0,0,300,320);
 for(var side=-1;side<=1;side+=2){ring(150+side*49,158,55,96,'#164164');ring(150+side*49,158,57,98,'#0a223c');ring(150+side*121,158,13,59,'#175273');
 line(150+side*77,79,150+side*114,40,'#2585ac',2);line(150+side*114,40,150+side*135,35,'#62c8df',1);}
 for(var i=0;i<M;i++){var p=pts[i],w=moving?1:0;projected[i].x=150+p.x+Math.sin(t*.7+p.phase)*3*w;projected[i].y=158+p.y+Math.cos(t*.6+p.phase)*2*w;}
 for(var i=0;i<M;i+=15){var p=projected[i],q=projected[(i+47)%M];line(p.x,p.y,q.x,q.y,'#10334f',.6);
 if(moving){var u=(frame*.075+i*.013)%1;c.fillStyle='#ffcc77';c.fillRect(p.x+(q.x-p.x)*u-1,p.y+(q.y-p.y)*u-1,2.5,2.5);}}
 c.fillStyle='#3987ab';for(var i=0;i<M;i++){var p=projected[i];c.fillRect(p.x,p.y,1.1,1.1);}
 c.fillStyle='#9aeaff';for(var i=0;i<M;i+=7){var p=projected[i];c.fillRect(p.x-.4,p.y-.4,1.8,1.8);}
 if(moving){c.fillStyle='#ffbd61';for(var i=0;i<M;i++){if(activity[i]>.22){var p=projected[i];c.fillRect(p.x-1,p.y-1,2.4,2.4);}}}
 for(var i=0;i<M;i+=37){var p=projected[i],e=moving?activity[i]:0;c.beginPath();c.arc(p.x,p.y,4+e*4,0,6.29);c.fillStyle=e>.15?'#6b452c':'#123d56';c.fill();c.beginPath();c.arc(p.x,p.y,1.8+e,0,6.29);c.fillStyle=e>.15?'#fff1ad':'#a5efff';c.fill();}}
var button=document.getElementById('start');
function stop(){if(timer!==null)clearInterval(timer);timer=null;button.disabled=false;}
function animate(){frame++;step();draw(true);if(frame>=360)stop();}
button.onclick=function(){if(timer!==null)return;frame=0;button.disabled=true;timer=setInterval(animate,125);animate();};
draw(false);TelegramWidget.ready();
</script></body></html>'''
    if len(html.encode()) > 32768 or len(zlib.compress(html.encode(), 9)) > 4096:
        raise ValueError('Native fly widget exceeds Telegram size limits')
    return html
