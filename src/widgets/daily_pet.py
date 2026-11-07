"""Private native petting UI; all coins and deadlines are server-owned."""
import json

from src.widgets.hedgehog import TEMPLATE, to_hedgehog_html


def to_daily_pet_html(token, images, snapshot):
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
    for left, top, angle in ((2, 42, -90), (-5, 72, -95), (-6, 108, -110), (0, 140, -120), (159, 42, 20), (164, 72, 30), (164, 108, 40), (155, 140, 55)):
        front = front.replace('<span class="ear">', f'<i class="spike" style="left:{left}px;top:{top}px;transform:rotate({angle}deg)"></i><span class="ear">')
    template = front + SCRIPT.replace('__SNAPSHOT__', json.dumps(snapshot, separators=(',', ':'))) + '</body></html>'
    # No gallery thumbnail: the ordinary full-size photo is already in the chat.
    return to_hedgehog_html(token, images / '__no_thumbnail__', template=template)


EXTRA_STYLE = '''
#heart{display:flex;gap:12px;padding:10px}#heart i{display:block;position:relative;width:14px;height:14px;background:#ed2149;transform:rotate(45deg)}#heart i:before,#heart i:after{content:"";position:absolute;width:14px;height:14px;background:#ed2149;border-radius:50%;left:-7px;top:0}#heart i:after{left:0;top:-7px}.paw{position:absolute;left:38px;top:142px;width:28px;height:25px;border:2px solid #111;background:white;border-radius:50%}.paw.r{left:111px}.joy .paw{transform:translateY(-12px)}.foot{height:20px;width:29px}.foot:after{content:"";position:absolute;left:9px;top:6px;width:11px;height:10px;background:white;border-radius:50%}body{color:#111}#scene{height:225px;width:280px}#animal{left:48px;top:20px}.quills{border:9px dotted #111}.belly{inset:34px 20px 4px}.eyes{top:73px;height:25px;width:21px;border:4px solid #111;background:#111;border-radius:50%}.eyes.r{left:105px}.eyes:after{content:"";position:absolute;background:white;width:6px;height:7px;border-radius:50%;left:1px;top:1px}.nose{top:105px}.mouth{top:120px}.cheek{top:115px}#heart{font-size:23px;right:8px;top:0;color:#ed2149}#hand{left:155px;top:139px;z-index:2}#hand:before,.fingers{display:none}#ripple{position:absolute;left:147px;top:130px;width:49px;height:49px;border:3px solid #ff6f85;border-radius:50%;opacity:0}.petted #ripple{opacity:1;transform:scale(1.4)}.joy #ripple{opacity:1;transform:scale(.8)}.petted .eyes,.joy .eyes{height:10px;background:white;border:3px solid #111;border-bottom:0;border-radius:20px 20px 0 0}.petted .eyes:after,.joy .eyes:after{display:none}.joy #animal{transform:rotate(5deg) translateY(-5px)}.joy #hand{transform:rotate(-24deg) translateY(-10px)}.joy #heart{opacity:1;transform:scale(1.2)}.joy .mouth{height:15px;width:21px;left:78px;background:#ed2149;border:3px solid #111;border-radius:0 0 15px 15px}#back{background:#111;color:#fff;width:100%;padding:13px;border:0;border-radius:24px}#photo{height:auto;width:auto;color:#ed2149;font-weight:bold}#pet{font-size:15px}#petting{color:#555}
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
