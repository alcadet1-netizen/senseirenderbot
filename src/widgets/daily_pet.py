"""Private native petting UI; all coins and deadlines are server-owned."""
import json
import re

from src.widgets.hedgehog import TEMPLATE, to_hedgehog_html


def to_daily_pet_html(token, images, snapshot, *, demo=False):
    front = TEMPLATE.split('<script>', 1)[0]
    for old, new in (
        ('7 сек', '10 сек'), ('за 7 секунд', 'пока не истекли 10 секунд'),
        ('Без спешки. Стандартный бонус ты получишь в любом случае.', 'Основная награда уже начислена. Успей добавить монет!'),
        ('Начать · 10 секунд', 'Погладить · +10%'),
        ('Одно поглаживание — +10% монет', 'Каждое подтверждённое поглаживание — +10% монет'),
    ):
        front = front.replace(old, new)
    front = front.replace('10 сек', '15 сек').replace('10 секунд', '15 секунд')
    front = re.sub(r'<style>.*?</style>', '<style>' + EXTRA_STYLE + '</style>', front, flags=re.S)
    front = front.replace('<img id="photo" src="__IMAGE__" alt="Картинка ежа к ежедневной награде">',
        '<p id="photo">♥ Спасибо за ласку!</p><button id="back" style="display:none">Вернуться в чат ↗</button>')
    # One canvas display list, not separately transformed CSS quills. Native
    # clients can disagree with browser transform-origin for zero-size borders.
    start = front.index('<button id="scene"')
    end = front.index('</button>', start) + len('</button>')
    front = front[:start] + '<button id="scene" aria-label="Погладить ежа"><canvas id="art" width="560" height="480"></canvas></button>' + front[end:]
    script = SCRIPT.replace('<script>', '<script>' + ART_SCRIPT, 1)
    if demo:
        # A local-only demo: no request method or usable payout token in the HTML.
        start = script.index('function ask(action){')
        end = script.index('function touch(){', start)
        script = script[:start] + DEMO_ASK + script[end:]
        script = script.replace('Основная награда и подтверждённые добавки сохранены.',
                                'Тест завершён. Награды не начислялись.')
        script = script.replace('Дополнительно начислено:', 'Тестовый бонус (без начисления):')
        script = script.replace('15 секунд общие с уведомлением в чате', 'Тест · 15 секунд · без наград')
        front = front.replace('Основная награда уже начислена. Успей добавить монет!',
                              'Тестовый виджет. Балансы и ежедневная попытка не меняются.')
        front = front.replace('Раз в день · 00:00 UTC · XP без изменений.', 'ТЕСТ · Награды не начисляются')
        token = 'A' * 32
    template = front + script.replace('__SNAPSHOT__', json.dumps(snapshot, separators=(',', ':'))) + '</body></html>'
    # No gallery thumbnail: the ordinary full-size photo is already in the chat.
    return to_hedgehog_html(token, images / '__no_thumbnail__', template=template)


EXTRA_STYLE = '''
*{box-sizing:border-box}body{margin:0;padding:16px;background:white;color:#17191d;font:14px sans-serif;text-align:center}header{display:flex;justify-content:space-between;font-size:11px;color:#76825d}#clock{border:1px solid #a2ab83;border-radius:20px;padding:5px 10px}h2{font-size:23px;font-weight:500;margin:16px 0 5px}p{font-size:12px;color:#82765e;margin:8px 0}button{font:600 15px sans-serif;cursor:pointer}#scene{display:block;width:280px;height:240px;margin:4px auto;padding:0;border:0;background:transparent}#art{width:280px;height:240px}#pet,#back{width:100%;padding:14px;border:0;border-radius:26px;background:#17191d;color:white}#note{min-height:28px;line-height:1.5}#petting,#bonus{font-size:11px;color:#748351}#photo{display:none;color:#ed2149}#reward{font-weight:bold;color:#17191d;line-height:1.5}.rules{font-size:10px;margin-top:12px}
'''


ART_SCRIPT = '''
var c=document.getElementById('art').getContext('2d');
function oval(x,y,rx,ry,fill,edge){c.beginPath();c.ellipse(x,y,rx,ry,0,0,7);c.fillStyle=fill;c.fill();if(edge){c.strokeStyle=edge;c.stroke();}}
function curve(points){c.beginPath();c.moveTo(points[0],points[1]);for(var i=2;i<points.length;i+=6)c.bezierCurveTo(points[i],points[i+1],points[i+2],points[i+3],points[i+4],points[i+5]);}
function heart(x,y){c.beginPath();c.moveTo(x,y+5);c.bezierCurveTo(x-20,y-8,x-11,y-22,x,y-12);c.bezierCurveTo(x+11,y-22,x+20,y-8,x,y+5);c.fillStyle='#ed2149';c.fill();c.strokeStyle='#17191d';c.stroke();}
function paint(n){
 c.setTransform(2,0,0,2,0,0);c.clearRect(0,0,280,240);c.lineWidth=2;c.lineJoin='round';c.lineCap='round';
 oval(140,222,77,7,'#e7e7e7');
 c.beginPath();
 for(var i=0;i<=40;i++){var a=(-210+i*6)*Math.PI/180,r=i%2?94:79,x=140+r*Math.cos(a),y=128+(i%2?104:89)*Math.sin(a);if(!i)c.moveTo(x,y);else c.lineTo(x,y);}
 c.quadraticCurveTo(220,230,140,230);c.quadraticCurveTo(60,230,71.6,172.5);c.closePath();c.fillStyle='#17191d';c.fill();
 oval(86,96,15,17,'white','#17191d');oval(194,96,15,17,'white','#17191d');
 oval(86,96,8,10,'#ff7187');oval(194,96,8,10,'#ff7187');
 oval(140,143,65,76,'white','#17191d');
 if(!n){oval(116,113,12,15,'#17191d');oval(164,113,12,15,'#17191d');oval(112,108,4,5,'white');oval(160,108,4,5,'white');oval(120,119,2,2,'white');oval(168,119,2,2,'white');}
 else{c.strokeStyle='#17191d';c.lineWidth=3;curve([104,115,108,104,119,104,124,114]);c.stroke();curve([156,114,161,104,172,104,176,115]);c.stroke();c.lineWidth=2;heart(213,56);heart(67,63);if(n===2)heart(239,95);}
 oval(104,135,11,5,'#ff8193');oval(176,135,11,5,'#ff8193');oval(140,130,7,4,'#17191d');
 if(n){curve([128,141,134,147,147,147,153,139,153,162,132,164,128,141]);c.fillStyle='#17191d';c.fill();oval(142,153,7,4,'#ed2149');}
 else{curve([126,141,132,147,137,145,140,140,143,145,148,147,154,141]);c.strokeStyle='#17191d';c.stroke();}
 var py=n===2?170:180;
 oval(104,py,15,12,'white','#17191d');oval(176,py,15,12,'white','#17191d');
 oval(107,211,20,17,'#17191d','white');oval(173,211,20,17,'#17191d','white');
 oval(107,215,8,7,'white');oval(173,215,8,7,'white');
 for(var j=-1;j<=1;j++){oval(107+j*8,202,3,4,'white');oval(173+j*8,202,3,4,'white');}
 if(n){for(var k=0;k<3;k++){c.beginPath();c.arc(170,177,15+k*7+(n===2?3:0),0,7);c.strokeStyle=k===2?'#ffb3bd':'#ff7187';c.stroke();}}
 curve([218,244,205,227,188,207,174,187,160,172,155,161,164,156,173,150,183,163,191,175,196,182,201,189,207,195,224,190,237,203,246,216,253,226,259,235,264,244]);c.closePath();c.fillStyle='white';c.fill();c.strokeStyle='#17191d';c.stroke();
}
'''




SCRIPT = '''<script>
var token=__TOKEN__,data=__SNAPSHOT__,busy=false,ended=false,deadline=Infinity,clock=0,frame=0;
var pet=document.getElementById('pet'),scene=document.getElementById('scene'),note=document.getElementById('note');
function draw(){var left=Math.max(0,deadline-Date.now());document.getElementById('clock').textContent=Math.ceil(left/1000)+' сек';if(!left){clearInterval(clock);ended=true;scene.className=data.taps?'joy':'';paint(data.taps?2:0);document.getElementById('photo').style.display='block';document.getElementById('back').style.display='block';pet.textContent='Обновить результат';document.getElementById('title').textContent=data.taps?'Ёжик доволен':'Ёжик отдыхает';note.textContent='Основная награда и подтверждённые добавки сохранены.';}}
function show(r){
 if(r.error){note.textContent=r.error;return;}
 if(r.taps>=data.taps)data=r;
 deadline=Math.min(deadline,Date.now()+Math.max(0,r.remaining_ms));
 if(r.state==='done')deadline=0;
 document.getElementById('bonus').textContent='Поглаживаний: '+data.taps+' · +'+(data.taps*10)+'% монет';
 document.getElementById('reward').textContent='Дополнительно начислено: +'+data.extra_coins+' монет';
 document.getElementById('petting').textContent='15 секунд общие с уведомлением в чате';
 clearInterval(clock);draw();if(!ended)clock=setInterval(draw,100);
}
function ask(action){
 // Each tap must request during its own gesture, even while earlier replies wait.
 if(action!=='p'&&busy)return;if(action!=='p')busy=true;
 TelegramWidget.request('dp:'+action+':'+token).then(function(answer){
  if(action!=='p')busy=false;try{show(JSON.parse(answer.result));}catch(e){note.textContent='Ответ потерялся. Обнови результат: принятый бонус сохранён.';}
 },function(e){if(action!=='p')busy=false;note.textContent='Telegram ограничивает частоту запросов. Подтверждённые бонусы сохранены.';});
}
function touch(){
 if(TelegramWidget.isForward||TelegramWidget.isPreview)return;
 if(Date.now()>=deadline){draw();return;}
 if(ended)return;
 frame++;scene.className=frame%2?'petted':'joy';paint(frame%2?1:2);
 document.getElementById('title').textContent='Фыр-фыр!';
 ask('p');
}
document.body.onclick=touch;
pet.onclick=function(e){e.stopPropagation();if(ended)ask('v');else touch();};
document.getElementById('back').onclick=function(e){e.stopPropagation();TelegramWidget.openTelegramLink('https://t.me/airchatton');};
paint(0);show(data);
if(TelegramWidget.isForward||TelegramWidget.isPreview){clearInterval(clock);pet.disabled=true;scene.disabled=true;note.textContent='Открой личную ссылку со своего уведомления ежа.';document.getElementById('back').style.display='none';}
TelegramWidget.ready();
</script>'''


DEMO_ASK = """function ask(action){
 var count=data.taps+(action==='p'&&!ended?1:0);
 show({state:ended?'done':'playing',remaining_ms:Math.max(0,deadline-Date.now()),
       taps:count,extra_coins:Math.floor(55*count/10),base_coins:55});
}
"""
