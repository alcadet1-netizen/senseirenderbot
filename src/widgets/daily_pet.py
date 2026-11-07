"""Private native petting UI; all coins and deadlines are server-owned."""
import json

from src.widgets.hedgehog import TEMPLATE, to_hedgehog_html


def to_daily_pet_html(token, images, snapshot):
    front = TEMPLATE.split('<script>', 1)[0]
    for old, new in (
        ('7 сек', '10 сек'), ('за 7 секунд', 'пока не истекли 10 секунд'),
        ('Без спешки. Стандартный бонус ты получишь в любом случае.', 'Основная награда уже начислена. Успей добавить монет!'),
        ('Начать · 7 секунд', 'Погладить · +10%'),
        ('Одно поглаживание — +10% монет', 'Каждое подтверждённое поглаживание — +10% монет'),
    ):
        front = front.replace(old, new)
    template = front + SCRIPT.replace('__SNAPSHOT__', json.dumps(snapshot, separators=(',', ':'))) + '</body></html>'
    return to_hedgehog_html(token, images, template=template)


SCRIPT = '''<script>
var token=__TOKEN__,data=__SNAPSHOT__,busy=false,ended=false,deadline=0,clock=0;
var pet=document.getElementById('pet'),scene=document.getElementById('scene'),note=document.getElementById('note');
function draw(){var left=Math.max(0,deadline-Date.now());document.getElementById('clock').textContent=Math.ceil(left/1000)+' сек';if(!left){clearInterval(clock);ended=true;scene.style.display='none';document.getElementById('photo').style.display='block';pet.textContent='Обновить результат';scene.disabled=true;document.getElementById('title').textContent=data.taps?'Ёжик доволен':'Ёжик отдыхает';note.textContent='Время вышло. Основная награда сохранена, подтверждённые бонусы уже добавлены.';}}
function show(r){
 if(r.error){note.textContent=r.error;return;}
 data=r;ended=r.state==='done';deadline=Date.now()+r.remaining_ms;
 document.getElementById('bonus').textContent='Поглаживаний: '+r.taps+' · +'+(r.taps*10)+'% монет';
 document.getElementById('reward').textContent='Дополнительно начислено: +'+r.extra_coins+' монет';
 document.getElementById('petting').textContent='10 секунд общие с уведомлением в чате';
 pet.textContent=ended?'Обновить результат':'Погладить · +10%';scene.disabled=ended;if(!ended){scene.style.display='block';document.getElementById('photo').style.display='none';}
 if(r.taps){scene.className='petted';document.getElementById('title').textContent='Ёжик доволен';}
 clearInterval(clock);draw();if(!ended)clock=setInterval(draw,100);
}
function ask(action){
 if(busy)return;busy=true;pet.disabled=true;scene.disabled=true;if(action==='p'){scene.className='';pet.textContent='Гладим…';}
 TelegramWidget.request('dp:'+action+':'+token).then(function(answer){
  busy=false;pet.disabled=false;scene.disabled=ended;
  try{show(JSON.parse(answer.result));}catch(e){note.textContent='Ответ потерялся. Обнови результат: принятый бонус сохранён.';}
 },function(e){busy=false;pet.disabled=false;scene.disabled=ended;note.textContent='Запрос не принят: '+e.code+'. Telegram ограничивает частоту; попробуй ещё раз.';});
}
pet.onclick=scene.onclick=function(){ask(ended?'v':'p');};
show(data);
if(TelegramWidget.isForward||TelegramWidget.isPreview){clearInterval(clock);pet.disabled=true;scene.disabled=true;note.textContent='Открой личную ссылку со своего уведомления ежа.';}
TelegramWidget.ready();
</script>'''
