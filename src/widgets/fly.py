"""Procedural synthetic fly-inspired network, not measured anatomy or bot telemetry."""
import zlib


def fly_html():
    html = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;padding:22px 12px 18px;background:#030b17;color:#d9f5ff;font:12px sans-serif;text-align:center}h2{margin:0;color:#e8faff;font-size:19px;letter-spacing:4px;font-weight:600}p{margin:10px 0 0;color:#77abc5;font-size:11px;line-height:1.5}canvas{display:block;width:300px;height:320px;margin:8px auto}button{width:292px;padding:15px 8px;border:1px solid #2784aa;border-radius:14px;background:#0b3049;color:#dffaff;font:13px sans-serif}button:disabled{background:#071d30;color:#70a2b9}
</style></head><body><h2>Sensei FLY LAB</h2><p>Визуальная симуляция нейронной сети мухи</p><canvas id="net" width="300" height="320"></canvas><button id="start">Запустить симуляцию нейронов</button>
<script>
// Synthetic, deterministic geometry and rate dynamics; no connectome or chat data.
var c=document.getElementById('net').getContext('2d'),N=1000,pts=[],screen=[],v=[],next=[],edges=[],seed=731,frame=0,timer=null;
function rnd(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;}
for(var i=0;i<N;i++){var side=i<500?-1:1,k=i%500,a=k*2.399963,r=Math.sqrt((k+.5)/500),z=(rnd()-.5)*36;
 var x=side*(40+Math.cos(a)*43*r),y=-18+Math.sin(a)*71*r;
 if(k>350){x=side*(53+Math.cos(a)*35*r);y=49+Math.sin(a)*28*r;}
 pts.push({x:x,y:y,z:z,phase:rnd()*6.28});screen.push({x:0,y:0});v.push(0);next.push(0);
 var base=i<500?0:500;edges.push([base+(k+1)%500,base+(k+7)%500,base+(k+31)%500,(i+500)%N]);}
function path(points,color,width){c.beginPath();for(var j=0;j<points.length;j++){if(j===0)c.moveTo(points[j][0],points[j][1]);else c.lineTo(points[j][0],points[j][1]);}c.strokeStyle=color;c.lineWidth=width;c.stroke();}
function oval(x,y,rx,ry,color,width){var p=[];for(var j=0;j<=20;j++){var a=j*6.283185/20;p.push([x+Math.cos(a)*rx,y+Math.sin(a)*ry]);}path(p,color,width);}
function shell(t){for(var side=-1;side<=1;side+=2){
 oval(150+side*48,143,57,83,'#09213b',9);oval(150+side*48,143,57,83,'#123d60',2);oval(150+side*48,143,55,81,'#28648a',.6);
 oval(150+side*118,151,17,58,'#123d60',1);
 for(var r=0;r<13;r++)for(var q=0;q<4;q++){var yy=105+r*7,xx=150+side*(111+q*4);if(Math.abs(yy-151)<47-q*4){c.fillStyle='#265373';c.fillRect(xx,yy,1,2);};}
 var p=[];for(var j=0;j<=30;j++){var u=j/30;p.push([150+side*(62+u*66),78-38*Math.sin(u*1.8)]);}path(p,'#103556',5);path(p,'#3c96bc',.7);
 for(var j=0;j<6;j++){var u=j/7;path([[150+side*(65+u*66),74-38*Math.sin(u*1.8)],[150+side*(64+u*66),82-38*Math.sin(u*1.8)]],'#52c7e7',.7);}
 }
 path([[139,220],[143,253],[150,282],[157,253],[161,220]],'#123b59',4);
 path([[139,220],[143,253],[150,282],[157,253],[161,220]],'#3d91b6',.7);
}
function draw(animated){var t=frame*.065;c.fillStyle='#030b17';c.fillRect(0,0,300,320);shell(t);
 for(var i=0;i<N;i++){var p=pts[i],w=animated?1:0;screen[i].x=150+p.x+Math.sin(t+p.phase)*1.7*w+p.z*Math.sin(t*.16)*.22;screen[i].y=151+p.y+Math.cos(t*.8+p.phase)*1.3*w;}
 for(var i=0;i<N;i++){var input=0;for(var j=0;j<4;j++){var k=edges[i][j];input+=v[k]*(k%5===0?-.26:.19);}
 next[i]=animated?Math.max(0,Math.min(1,v[i]*.56+input+(i%167===Math.floor(frame/9)%167?.7:0))):0;}
 for(var i=0;i<N;i++){var p=screen[i];if(i%12===0){var q=screen[edges[i][1]];path([[p.x,p.y],[q.x,q.y]],'#12334c',.45);}
 if(animated&&v[i]>.12&&i%24===0){var q=screen[edges[i][2]],u=(frame%16)/16;
 path([[p.x,p.y],[q.x,q.y]],'#845529',.6);c.beginPath();c.arc(p.x+(q.x-p.x)*u,p.y+(q.y-p.y)*u,1.2,0,6.29);c.fillStyle='#ffcc72';c.fill();}
 c.fillStyle=v[i]>.2?'#ffc974':(i%7===0?'#8ae6ff':'#245a7b');var size=v[i]>.2?1.6:1;c.fillRect(p.x,p.y,size,size);}
 for(var i=0;i<N;i+=41){var p=screen[i],e=animated?v[i]:0;for(var g=3;g>=1;g--){c.beginPath();c.arc(p.x,p.y,2+g*2+e*3,0,6.29);c.fillStyle=g===3?'#102e42':g===2?'#25516a':'#7dbcc9';c.fill();}c.beginPath();c.arc(p.x,p.y,1.7+e*2,0,6.29);c.fillStyle=e>.12?'#fff0a8':'#b6edff';c.fill();}
 for(var i=0;i<N;i++)v[i]=next[i];}
var button=document.getElementById('start');button.onclick=function(){if(timer!==null)return;frame=0;for(var i=0;i<N;i++)v[i]=0;button.disabled=true;draw(true);timer=setInterval(function(){frame++;draw(true);if(frame>=540){clearInterval(timer);timer=null;button.disabled=false;}},83);};
draw(false);TelegramWidget.ready();
</script></body></html>'''
    if len(html.encode()) > 32768 or len(zlib.compress(html.encode(), 9)) > 4096:
        raise ValueError('Native fly widget exceeds Telegram size limits')
    return html
