"""Native tap game with server-owned rewards; no WebApp SDK or fetch."""
import base64
import hashlib
import io
import json
import re
import zlib
from pathlib import Path

from PIL import Image, ImageOps


def to_hedgehog_html(token: str, images_dir: Path) -> str:
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{32}', token):
        raise ValueError('Invalid daily token')
    pictures = sorted(p for p in images_dir.glob('*') if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif'})
    candidates = ['']
    if pictures:
        selected = pictures[int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(pictures)]
        candidates = []
        with Image.open(selected) as original:
            for size, quality in ((128, 30), (96, 25), (64, 22)):
                thumb = ImageOps.contain(original.convert('RGB'), (size, size))
                buffer = io.BytesIO()
                thumb.save(buffer, 'JPEG', quality=quality, optimize=True)
                candidates.append('data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii'))
    for image in candidates:
        html = TEMPLATE.replace('__TOKEN__', json.dumps(token)).replace('__IMAGE__', image)
        if len(html.encode()) <= 32768 and len(zlib.compress(html.encode(), 9)) <= 4096:
            return html
    raise ValueError('Hedgehog exceeds native widget size limits')


TEMPLATE = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;padding:16px;font:14px sans-serif;color:var(--tg-theme-text-color);background:var(--tg-theme-bg-color)}
h2{font-size:21px;margin:0 0 8px}p{margin:8px 0;color:var(--tg-theme-hint-color);font-size:12px}
button{display:block;width:100%;padding:16px;border:0;border-radius:18px;background:var(--tg-theme-button-color);color:var(--tg-theme-button-text-color);font-size:16px}
#pet{margin:12px 0;font-size:44px;height:112px}#petting{font-size:12px;display:block}#photo{display:none;width:160px;height:160px;object-fit:contain;margin:8px auto;border-radius:14px}
#clock{font-weight:bold}#reward{font-size:15px;color:var(--tg-theme-text-color)}#note{min-height:32px}button:disabled{opacity:.7}
</style></head><body><h2>Погладь ежа</h2><p>12 секунд · до +50% монет за ласку</p>
<button id="pet">🦔<span id="petting">Начать 12 секунд</span></button>
<p id="clock">12 сек</p><p id="note">Можно просто отдохнуть — стандартный бонус твой.</p>
<img id="photo" src="__IMAGE__"><p id="reward"></p>
<p id="bonus">За поглаживания: +0% монет</p><p>Одно зачтённое поглаживание: +10%, максимум +50%.<br>Одна попытка в день · 00:00 UTC. XP без изменений.</p>
<script>
var token=__TOKEN__,busy=false,playing=false,left=0,deadline=0,clock=0,pets=0,sequence=0,lastSend=0,bonus=0;
var pet=document.getElementById('pet'),label=document.getElementById('petting'),note=document.getElementById('note');
function draw(){document.getElementById('clock').textContent=left>0?Math.ceil(left/1000)+' сек':'Готово';if(left<=0)label.textContent='Забрать награду';}
function show(data){
 if(data.error){note.textContent=data.error;return;}
 if(data.state==='done'){
 playing=false;clearInterval(clock);pet.disabled=true;label.textContent='До завтра!';document.getElementById('clock').textContent='Готово';
 var r=data.result;note.textContent=r.message;
 document.getElementById('reward').textContent=r.success?'+'+r.total_xp+' XP · +'+r.total_coins+' монет · Серия: '+r.streak:'Серия: 0 · Ничего не списано';
 if(r.tap_bonus_coins)document.getElementById('reward').textContent+=' · В том числе за ласку: +'+r.tap_bonus_coins;
 if(r.success)document.getElementById('photo').style.display='block';return;
 }
 sequence=Math.max(sequence,data.tap_seq||0);bonus=data.bonus_percent||0;document.getElementById('bonus').textContent='За поглаживания: +'+bonus+'% монет';
 playing=true;left=data.remaining_ms;deadline=Date.now()+left;label.textContent='Гладь спинку ежа';
 clearInterval(clock);draw();clock=setInterval(function(){left=Math.max(0,deadline-Date.now());draw();if(!left)clearInterval(clock);},250);
}
function ask(action){
 busy=true;
 TelegramWidget.request('hg:'+action+':'+token).then(function(answer){busy=false;try{show(JSON.parse(answer.result));}catch(e){note.textContent='Ёж потерял ответ. Погладь ещё раз — повторной награды не будет.';}},function(e){busy=false;note.textContent='Связь с ежом: '+e.code+'. Нажми ещё раз.';});
}
pet.onclick=function(){
 if(busy)return;
 if(!playing){lastSend=Date.now();ask('s');return;}
 if(left<=0){ask('f');return;}
 pets++;pet.style.transform=pets%2?'scale(0.97)':'scale(1)';
 if(bonus<50&&Date.now()-lastSend>=1500){lastSend=Date.now();sequence++;ask('t'+sequence);}
 note.textContent=pets%2?'Фыр-фыр! Кажется, ему нравится.':'Осторожно, не против колючек!';
};
if(TelegramWidget.isForward||TelegramWidget.isPreview){pet.disabled=true;note.textContent='Вызови /senseidaily у бота для своей попытки.';}
TelegramWidget.ready();
</script></body></html>'''
