"""Native tap game with server-owned rewards; no WebApp SDK or fetch."""
import base64
import hashlib
import io
import json
import re
import zlib
from pathlib import Path

from PIL import Image, ImageOps


def to_hedgehog_html(token: str, images_dir: Path, *, template=None) -> str:
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}', token):
        raise ValueError('Invalid daily token')
    pictures = sorted(p for p in images_dir.glob('*') if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif'})
    candidates = ['']
    if pictures:
        selected = pictures[int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(pictures)]
        candidates = []
        with Image.open(selected) as original:
            for size, quality in ((128, 30), (96, 25), (64, 18), (48, 18), (32, 16)):
                thumb = ImageOps.contain(original.convert('RGB'), (size, size))
                buffer = io.BytesIO()
                thumb.save(buffer, 'JPEG', quality=quality, optimize=True)
                candidates.append('data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii'))
    for image in candidates:
        html = (TEMPLATE if template is None else template).replace('__TOKEN__', json.dumps(token)).replace('__IMAGE__', image)
        if len(html.encode()) <= 32768 and len(zlib.compress(html.encode(), 9)) <= 3900:
            return html
    raise ValueError('Hedgehog exceeds native widget size limits')


TEMPLATE = '''<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;background:#faf1e2;color:#463a2d;font:14px sans-serif;padding:16px;text-align:center}
header{display:flex;justify-content:space-between;align-items:center;color:#7c8761;font-size:10px;letter-spacing:1px}#clock{border:1px solid #a2ab83;border-radius:20px;padding:5px 10px;letter-spacing:0}h2{font-size:22px;font-weight:500;margin:18px 0 5px}p{margin:8px 0;font-size:12px;color:#82765e}button{font:600 17px sans-serif;cursor:pointer}#scene{height:205px;position:relative;margin:4px auto;width:260px;display:block;border:0;background:transparent;padding:0}
#animal{position:absolute;left:43px;top:16px;width:174px;height:180px;transform-origin:50% 90%;transition:transform .2s}.quills{position:absolute;inset:0;border-radius:47% 47% 38% 38%;background:#77513b;border:7px dotted #a07150}.spike{position:absolute;top:-10px;width:18px;height:40px;background:#77513b;border-radius:90% 0 90% 0;transform:rotate(-35deg)}.belly{position:absolute;inset:47px 23px 5px;border-radius:45% 45% 42% 42%;background:#f4d6ae;border:2px solid #d5aa81}.ear{position:absolute;top:46px;width:31px;height:32px;border:7px solid #f4d6ae;background:#dcae88;border-radius:50%;left:17px}.ear.r{left:auto;right:17px}.eyes{position:absolute;left:51px;top:83px;width:19px;height:12px;border:2px solid #523b2b;border-top:0;border-radius:0 0 18px 18px}.eyes.r{left:104px}.nose{position:absolute;top:99px;left:80px;width:16px;height:11px;background:#63432d;border-radius:50%}.mouth{position:absolute;left:82px;top:112px;width:13px;height:7px;border-bottom:2px solid #63432d;border-radius:50%}.cheek{position:absolute;left:44px;top:108px;width:20px;height:12px;background:#edaa91;border-radius:50%}.cheek.r{left:112px}.foot{position:absolute;bottom:1px;left:37px;width:26px;height:12px;background:#d2a17c;border-radius:50%}.foot.r{left:114px}
#hand{position:absolute;left:139px;top:105px;width:51px;height:85px;background:#edb08d;border:2px solid #d59476;border-radius:24px 24px 6px 6px;transform:rotate(-30deg);transform-origin:50% 100%;pointer-events:none;transition:transform .2s}#hand:before{content:"";position:absolute;left:-14px;top:14px;width:22px;height:55px;background:#edb08d;border:2px solid #d59476;border-radius:20px;transform:rotate(-25deg)}.fingers{position:absolute;left:5px;top:-12px;width:9px;height:53px;background:#f2bb99;border-radius:10px;border:1px solid #d59476}.fingers.b{left:17px;top:-18px}.fingers.c{left:29px;top:-12px}#heart{position:absolute;top:4px;right:26px;font-size:27px;color:#bd7e73;opacity:0}.petted #animal{transform:scale(1.025,.97)}.petted #hand{transform:rotate(-24deg) translateY(-8px)}.petted #heart{opacity:1}
#pet{width:100%;border:0;border-radius:28px;background:#99a776;color:#fff;padding:14px;min-height:48px}#pet:disabled{background:#b6bca3;cursor:default}#note{min-height:28px;line-height:1.45}#bonus{font-size:11px;color:#748351}#photo{display:none;width:150px;height:130px;object-fit:contain;border-radius:18px;margin:8px auto}#reward{font-weight:bold;color:#53673b;line-height:1.5}.rules{font-size:10px;line-height:1.5;margin:10px 0 0}#petting{font-size:11px;color:#82765e;display:block}@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body><header><span>SENSEI</span><span id="clock">7 сек</span></header>
<h2 id="title">Ёжик ждёт ласки</h2><p>Успей погладить его за 7 секунд</p>
<button id="scene" aria-label="Погладить ежа"><span id="animal"><span class="quills"></span><i class="spike" style="left:24px;top:7px"></i><i class="spike" style="left:43px;top:-3px"></i><i class="spike" style="left:63px;top:-9px"></i><i class="spike" style="left:83px;top:-11px"></i><i class="spike" style="left:103px;top:-7px"></i><i class="spike" style="left:123px;top:0px"></i><i class="spike" style="left:141px;top:15px"></i><span class="ear"></span><span class="ear r"></span><span class="belly"></span><span class="eyes"></span><span class="eyes r"></span><span class="nose"></span><span class="mouth"></span><span class="cheek"></span><span class="cheek r"></span><span class="foot"></span><span class="foot r"></span></span><span id="hand"><span class="fingers"></span><span class="fingers b"></span><span class="fingers c"></span></span><span id="heart">♡</span></button>
<span id="petting">Твой маленький колючий приятель</span><p id="note" role="status">Без спешки. Стандартный бонус ты получишь в любом случае.</p>
<button id="pet">Начать · 7 секунд</button><p id="bonus">Одно поглаживание — +10% монет</p>
<img id="photo" src="__IMAGE__" alt="Картинка ежа к ежедневной награде"><p id="reward"></p>
<p class="rules">Раз в день · 00:00 UTC · XP без изменений.</p>
<script>
var token=__TOKEN__,busy=false,playing=false,left=0,deadline=0,clock=0,bonus=0;
var pet=document.getElementById('pet'),scene=document.getElementById('scene'),label=document.getElementById('petting'),note=document.getElementById('note');
function draw(){document.getElementById('clock').textContent=left>0?Math.ceil(left/1000)+' сек':'Готово';if(left<=0){pet.textContent='Забрать награду';label.textContent='Ритуал завершён';}}
function show(data){
 if(data.error){note.textContent=data.error;return;}
 if(data.state==='done'){
 playing=false;clearInterval(clock);pet.disabled=true;pet.textContent='До завтра!';document.getElementById('clock').textContent='Готово';
 var r=data.result;note.textContent=r.message;
 document.getElementById('title').textContent=r.tap_count?'Ёжик доволен':'Спасибо за компанию';
 document.getElementById('reward').textContent=r.success?'+'+r.total_xp+' XP · +'+r.total_coins+' монет · Серия: '+r.streak:'Серия: 0 · Ничего не списано';
 if(r.tap_bonus_coins)document.getElementById('reward').textContent+=' · В том числе за ласку: +'+r.tap_bonus_coins;
 scene.style.display='none';label.style.display='none';
 if(r.success)document.getElementById('photo').style.display='block';return;
 }
 bonus=data.bonus_percent||0;document.getElementById('bonus').textContent=bonus?'За поглаживание: +'+bonus+'% монет':'Одно поглаживание — +10% монет';
 if(bonus){scene.className='petted';document.getElementById('title').textContent='Ёжик доволен';}
 playing=true;left=data.remaining_ms;deadline=Date.now()+left;pet.textContent=bonus?'Ёжик доволен ♡':'Погладить';label.textContent='Коснись ёжика или зелёной кнопки';
 clearInterval(clock);draw();clock=setInterval(function(){left=Math.max(0,deadline-Date.now());draw();if(!left)clearInterval(clock);},200);
}
function ask(action){
 busy=true;
 TelegramWidget.request('hg:'+action+':'+token).then(function(answer){busy=false;try{show(JSON.parse(answer.result));}catch(e){note.textContent='Ответ потерялся. Нажми ещё раз — награда не удвоится.';}},function(e){busy=false;note.textContent='Связь с ежом: '+e.code+'. Нажми ещё раз.';});
}
function touch(){
 if(busy)return;
 if(!playing){ask('s');return;}
 if(Date.now()>=deadline){ask('f');return;}
 scene.className='petted';note.textContent='Фыр-фыр! Кажется, ему нравится.';
 if(!bonus)ask('t1');
}
pet.onclick=scene.onclick=touch;
if(TelegramWidget.isForward||TelegramWidget.isPreview){pet.disabled=true;scene.disabled=true;note.textContent='Вызови /senseidaily у бота для своей попытки.';}
TelegramWidget.ready();
</script></body></html>'''
