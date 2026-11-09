"""Self-contained native canvas lab; synthetic nodes, no connectome claims."""
import zlib


def fly_html():
    html = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;padding:18px;background:#101820;color:#e4f6ed;font:14px sans-serif}h2{margin:0 0 8px;color:#aaf0be}p{line-height:1.5;font-size:12px}canvas{width:280px;height:210px}button{padding:12px;border:0;border-radius:16px;background:#aaf0be;color:#101820;margin:3px}#why{min-height:55px;color:#aaf0be}
</style></head><body><h2>Sensei · Fly Lab</h2><p>1000 синтетических узлов, 4000 направленных связей. Не коннектом и не симуляция настоящего мозга мухи.</p>
<canvas id="net" width="280" height="210"></canvas>
<p id="stats"></p><p>Сигнал → новизна → торможение → выбор реакции</p>
<button id="new">Новая тема</button><button id="repeat">Повтор</button><button id="rest">Покой</button>
<p id="why">Нажми «Новая тема»: сигнал пройдёт через условные нейроны.</p>
<p>В чате: редкая реплика или вопрос. Решение ограничено паузами и лимитами MongoDB. Здесь показана только локальная демонстрация, без чтения переписки и без наград.</p>
<script>
var c=document.getElementById('net').getContext('2d'),N=1000,tick=0,pulse=0,running=false,timer=null;
var pts=[],v=[],next=[],edges=[],seed=731;
function rnd(){seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;}
for(var i=0;i<N;i++){var angle=i*2.39996,r=96*Math.sqrt((i+.5)/N);pts.push({x:140+1.3*r*Math.cos(angle),y:105+r*Math.sin(angle)});v.push(0);next.push(0);var e=[];for(var j=0;j<4;j++)e.push(Math.floor(rnd()*N));edges.push(e);}
function draw(){c.clearRect(0,0,280,210);var active=0;for(var i=0;i<N;i++){var input=0;for(var j=0;j<4;j++){var k=edges[i][j];input+=v[k]*(k%5===0?-.32:.24);}next[i]=Math.max(0,Math.min(1,v[i]*.72+input+(pulse>0&&i<50?.8:0)));}
for(var i=0;i<N;i++){v[i]=next[i];if(v[i]>.15){active++;if(i%8===0){var q=pts[edges[i][0]];c.beginPath();c.moveTo(pts[i].x,pts[i].y);c.lineTo(q.x,q.y);c.strokeStyle='#355847';c.stroke();}}c.beginPath();c.arc(pts[i].x,pts[i].y,v[i]>.15?1.8:1,0,6.29);c.fillStyle=v[i]>.15?(i%5===0?'#ffb275':'#aaf0be'):'#355047';c.fill();}pulse=Math.max(0,pulse-1);tick++;document.getElementById('stats').textContent='1000 узлов · 4000 связей · активны '+active+' · шаг '+tick;}
function stop(){clearInterval(timer);timer=null;running=false;}
function start(){if(running)return;running=true;var frames=0;timer=setInterval(function(){draw();frames++;if(frames>=300){stop();document.getElementById('why').textContent='Анимация приостановлена для экономии ресурсов. Кнопка запускает новый цикл.';}},150);}
function stimulus(repeat){pulse=repeat?1:8;document.getElementById('why').textContent=repeat?'Привыкание: короткий импульс, затем затухание. Это синтетическая модель.':'Новизна: импульс распространяется по возбуждающим и тормозным связям. Не данные реального мозга и не управление ботом.';draw();start();}
document.getElementById('new').onclick=function(){stimulus(false);};document.getElementById('repeat').onclick=function(){stimulus(true);};document.getElementById('rest').onclick=function(){stop();pulse=0;for(var i=0;i<N;i++)v[i]=0;document.getElementById('why').textContent='Покой. Нет подходящего сигнала — нет реплики.';draw();};
pulse=5;draw();start();TelegramWidget.ready();
</script></body></html>'''
    if len(html.encode()) > 32768 or len(zlib.compress(html.encode(), 9)) > 4096:
        raise ValueError('Native fly widget exceeds Telegram size limits')
    return html
