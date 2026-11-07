"""Private native petting UI; all coins and deadlines are server-owned."""
import json
import math
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
    # Adapted CSS illustration: no blurred raster inside the native 4 KiB budget.
    palette = {'#faf1e2':'#fff', '#463a2d':'#111', '#77513b':'#111',
        '#a07150':'#111', '#f4d6ae':'#fff', '#d5aa81':'#111', '#dcae88':'#ff7187',
        '#523b2b':'#111', '#63432d':'#111', '#edaa91':'#ff8193', '#d2a17c':'#111',
        '#edb08d':'#fff', '#d59476':'#111', '#f2bb99':'#fff', '#bd7e73':'#ed2149',
        '#99a776':'#171717', '#53673b':'#111'}
    for old, new in palette.items():
        front = front.replace(old, new)
    front = front.replace('</style>', EXTRA_STYLE + '</style>')
    front = front.replace('♡</span></button>', '<i></i><i></i><i></i></span><span id="ripple"></span></button>')
    front = front.replace('<img id="photo" src="__IMAGE__" alt="Картинка ежа к ежедневной награде">',
        '<p id="photo">♥ Спасибо за ласку!</p><button id="back" style="display:none">Вернуться в чат ↗</button>')
    front = front.replace('<span class="nose">', '<span class="paw"></span><span class="paw r"></span><span class="nose">')
    # One centred ellipse and evenly spaced radial quills, instead of the old
    # hand-positioned leaves. Faces/paws share a mirrored centreline at x=87.
    front = re.sub(r'<i class="spike"[^>]*></i>', '', front)
    quills = []
    for angle in range(-210, 31, 12):
        radians = math.radians(angle)
        left = 87 + 74 * math.cos(radians) - 8
        top = 98 + 80 * math.sin(radians) - 27
        quills.append(f'<i class="spike" style="left:{left:.1f}px;top:{top:.1f}px;transform:rotate({angle + 90}deg)"></i>')
    front = front.replace('<span class="quills">', ''.join(quills) + '<span class="quills">')
    script = SCRIPT
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
body{color:#17191d}#scene{height:235px;width:280px;max-width:100%}#animal{left:53px;top:24px;width:174px;height:180px;transform-origin:50% 85%}.spike{width:0;height:0;background:transparent;border-left:8px solid transparent;border-right:8px solid transparent;border-bottom:27px solid #17191d;border-radius:0;transform-origin:50% 100%}.quills{inset:6px 2px 0;border:0;border-radius:49% 49% 43% 43%;background:#17191d}.belly{inset:37px 20px 10px;border:2px solid #17191d;border-radius:48% 48% 44% 44%}.ear{top:37px;left:17px;width:28px;height:30px;border:6px solid white}.ear.r{left:auto;right:17px}.eyes{left:53px;top:76px;width:19px;height:23px;background:#17191d;border:0;border-radius:50%}.eyes.r{left:102px}.eyes:after{content:"";position:absolute;left:5px;top:4px;width:6px;height:7px;border-radius:50%;background:white}.nose{left:80px;top:105px;width:14px;height:10px;background:#17191d}.mouth{left:77px;top:117px;width:20px;height:9px;border-color:#17191d}.cheek{left:45px;top:110px;width:20px;height:10px}.cheek.r{left:109px}.paw{position:absolute;left:44px;top:138px;width:25px;height:22px;border:2px solid #17191d;border-radius:50%;background:white}.paw.r{left:105px}.foot{bottom:0;left:43px;width:28px;height:20px;background:#17191d}.foot.r{left:103px}.foot:after{content:"";position:absolute;left:8px;top:6px;width:12px;height:9px;border-radius:50%;background:white}#hand{left:160px;top:163px;width:31px;height:67px;border:2px solid #17191d;border-radius:18px 18px 7px 7px;transform:rotate(-30deg);z-index:2}#hand:before,.fingers{display:none}#ripple{position:absolute;left:144px;top:146px;width:42px;height:42px;border:2px solid #ff7187;border-radius:50%;opacity:0}#heart{display:flex;gap:12px;padding:10px;right:6px;top:3px}#heart i{position:relative;display:block;width:13px;height:13px;background:#ed2149;transform:rotate(45deg)}#heart i:before,#heart i:after{content:"";position:absolute;left:-6px;top:0;width:13px;height:13px;background:#ed2149;border-radius:50%}#heart i:after{left:0;top:-6px}.petted .eyes,.joy .eyes{height:10px;background:white;border:3px solid #17191d;border-bottom:0;border-radius:20px 20px 0 0}.petted .eyes:after,.joy .eyes:after{display:none}.petted #hand{transform:rotate(-25deg) translateY(-4px)}.petted #ripple{opacity:1;transform:scale(1.25)}.joy #animal{transform:translateY(-4px) scale(1.025)}.joy #hand{transform:rotate(-30deg) translateY(-7px)}.joy #heart{opacity:1;transform:scale(1.1)}.joy #ripple{opacity:1;transform:scale(.85)}.joy .paw{transform:translateY(-5px)}.joy .mouth{left:78px;width:18px;height:15px;background:#ed2149;border:2px solid #17191d;border-radius:0 0 12px 12px}#back{width:100%;padding:13px;border:0;border-radius:24px;background:#17191d;color:white}#photo{height:auto;width:auto;color:#ed2149;font-weight:bold}#pet{font-size:15px}#petting{color:#555}
'''




SCRIPT = '''<script>
var token=__TOKEN__,data=__SNAPSHOT__,busy=false,ended=false,deadline=Infinity,clock=0,frame=0;
var pet=document.getElementById('pet'),scene=document.getElementById('scene'),note=document.getElementById('note');
function draw(){var left=Math.max(0,deadline-Date.now());document.getElementById('clock').textContent=Math.ceil(left/1000)+' сек';if(!left){clearInterval(clock);ended=true;scene.className=data.taps?'joy':'';document.getElementById('photo').style.display='block';document.getElementById('back').style.display='block';pet.textContent='Обновить результат';document.getElementById('title').textContent=data.taps?'Ёжик доволен':'Ёжик отдыхает';note.textContent='Основная награда и подтверждённые добавки сохранены.';}}
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
 if(busy)return;busy=true;
 TelegramWidget.request('dp:'+action+':'+token).then(function(answer){
  busy=false;try{show(JSON.parse(answer.result));}catch(e){note.textContent='Ответ потерялся. Обнови результат: принятый бонус сохранён.';}
 },function(e){busy=false;note.textContent='Telegram ограничивает частоту запросов. Подтверждённые бонусы сохранены.';});
}
function touch(){
 if(TelegramWidget.isForward||TelegramWidget.isPreview)return;
 if(Date.now()>=deadline){draw();return;}
 if(ended)return;
 frame++;scene.className=frame%2?'petted':'joy';
 document.getElementById('title').textContent='Фыр-фыр!';
 ask('p');
}
document.body.onclick=touch;
pet.onclick=function(e){e.stopPropagation();if(ended)ask('v');else touch();};
document.getElementById('back').onclick=function(e){e.stopPropagation();TelegramWidget.openTelegramLink('https://t.me/airchatton');};
show(data);
if(TelegramWidget.isForward||TelegramWidget.isPreview){clearInterval(clock);pet.disabled=true;scene.disabled=true;note.textContent='Открой личную ссылку со своего уведомления ежа.';document.getElementById('back').style.display='none';}
TelegramWidget.ready();
</script>'''


DEMO_ASK = """function ask(action){
 var count=data.taps+(action==='p'&&!ended?1:0);
 show({state:ended?'done':'playing',remaining_ms:Math.max(0,deadline-Date.now()),
       taps:count,extra_coins:Math.floor(55*count/10),base_coins:55});
}
"""
