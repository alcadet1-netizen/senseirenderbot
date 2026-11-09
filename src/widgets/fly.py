"""Self-contained native canvas lab; synthetic nodes, no connectome claims."""
import zlib


def fly_html():
    html = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;padding:18px;background:#101820;color:#e4f6ed;font:14px sans-serif}h2{margin:0 0 8px;color:#aaf0be}p{line-height:1.5;font-size:12px}canvas{width:280px;height:210px}button{padding:12px;border:0;border-radius:16px;background:#aaf0be;color:#101820;margin:3px}#why{min-height:55px;color:#aaf0be}
</style></head><body><h2>Sensei · Fly Lab</h2><p>Упрощённая модель внимания. Не коннектом и не симуляция настоящего мозга мухи.</p>
<canvas id="net" width="280" height="210"></canvas>
<p>Сигнал → новизна → торможение → выбор реакции</p>
<button id="new">Новая тема</button><button id="repeat">Повтор</button><button id="rest">Покой</button>
<p id="why">Нажми «Новая тема»: сигнал пройдёт через условные нейроны.</p>
<p>В чате: редкая реплика или вопрос. Решение ограничено паузами и лимитами MongoDB. Здесь показана только локальная демонстрация, без чтения переписки и без наград.</p>
<script>
var c=document.getElementById('net').getContext('2d'),phase=0,energy=0,mode=0;
var pts=[];for(var i=0;i<20;i++)pts.push({x:25+(i%5)*57,y:28+Math.floor(i/5)*50});
function draw(){c.clearRect(0,0,280,210);for(var i=0;i<20;i++){var p=pts[i];if(i%5<4){c.beginPath();c.moveTo(p.x,p.y);c.lineTo(pts[i+1].x,pts[i+1].y);c.strokeStyle='#355847';c.stroke();}var active=energy>0&&i%5===phase%5;c.beginPath();c.arc(p.x,p.y,active?7:4,0,6.29);c.fillStyle=active?(mode===2?'#ffb275':'#aaf0be'):'#4b7460';c.fill();}phase++;energy=Math.max(0,energy-1);}
function stimulus(repeat){mode=repeat?2:1;energy=repeat?5:20;document.getElementById('why').textContent=repeat?'Привыкание: повторный сигнал подавлен. Выбор — промолчать.':'Новизна повысила внимание. Возможный выбор — короткий вопрос. В реальном чате всё ещё действуют лимиты.';draw();}
document.getElementById('new').onclick=function(){stimulus(false);};document.getElementById('repeat').onclick=function(){stimulus(true);};document.getElementById('rest').onclick=function(){energy=0;document.getElementById('why').textContent='Покой. Нет подходящего сигнала — нет реплики.';draw();};
draw();var timer=setInterval(draw,180);setTimeout(function(){clearInterval(timer);},45000);TelegramWidget.ready();
</script></body></html>'''
    if len(html.encode()) > 32768 or len(zlib.compress(html.encode(), 9)) > 4096:
        raise ValueError('Native fly widget exceeds Telegram size limits')
    return html
