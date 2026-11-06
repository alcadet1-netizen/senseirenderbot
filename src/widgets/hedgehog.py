"""Self-contained native widget. No WebApp SDK, network, or client-owned roll."""
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
    image = ''
    if pictures:
        selected = pictures[int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(pictures)]
        with Image.open(selected) as original:
            # Widgets cannot load the old picture URL. Embed a small version of
            # that exact asset, within Telegram's 4 KiB compressed HTML limit.
            thumb = ImageOps.contain(original.convert('RGB'), (64, 64))
            buffer = io.BytesIO()
            thumb.save(buffer, 'JPEG', quality=22, optimize=True)
            image = 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
    html = TEMPLATE.replace('__TOKEN__', json.dumps(token)).replace('__IMAGE__', image)
    if len(html.encode()) > 32768 or len(zlib.compress(html.encode(), 9)) > 4096:
        raise ValueError('Hedgehog exceeds native widget size limits')
    return html


TEMPLATE = '''<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;padding:16px;font:14px sans-serif;color:var(--tg-theme-text-color);background:var(--tg-theme-bg-color)}
h2{font-size:21px;margin:0 0 8px}p{margin:8px 0;color:var(--tg-theme-hint-color);font-size:12px}
button{display:block;width:100%;padding:16px;border:0;border-radius:18px;background:var(--tg-theme-button-color);color:var(--tg-theme-button-text-color);font-size:16px}
#pet{margin:12px 0;font-size:44px;height:112px}#petting{font-size:12px;display:block}#photo{display:none;width:96px;height:96px;object-fit:contain;margin:8px auto;border-radius:14px}
#clock{font-weight:bold}#reward{font-size:15px;color:var(--tg-theme-text-color)}#note{min-height:32px}button:disabled{opacity:.7}
</style></head><body><h2>Погладь ежа</h2><p>12 секунд нежности · 95% успеха</p>
<button id="pet">🦔<span id="petting">Поздороваться и погладить</span></button>
<p id="clock">12 сек</p><p id="note">Нажимай на ежа, чтобы гладить его.</p>
<img id="photo" src="__IMAGE__"><p id="reward"></p>
<p>Одна попытка в день · 00:00 UTC<br>5%: сброс серии. Монеты и XP не списываются.</p>
<script>
var token=__TOKEN__,busy=false,playing=false,left=0,deadline=0,clock=0,pets=0;
var pet=document.getElementById('pet'),label=document.getElementById('petting'),note=document.getElementById('note');
function draw(){document.getElementById('clock').textContent=left>0?Math.ceil(left/1000)+' сек':'Готово';if(left<=0)label.textContent='Погладить и узнать результат';}
function show(data){
 if(data.error){note.textContent=data.error;return;}
 if(data.state==='done'){
 playing=false;clearInterval(clock);pet.disabled=true;label.textContent='До завтра!';document.getElementById('clock').textContent='Готово';
 var r=data.result;note.textContent=r.message;
 document.getElementById('reward').textContent=r.success?'+'+r.total_xp+' XP · +'+r.total_coins+' монет · Серия: '+r.streak:'Серия: 0 · Ничего не списано';
 if(r.success)document.getElementById('photo').style.display='block';return;
 }
 playing=true;left=data.remaining_ms;deadline=Date.now()+left;label.textContent='Гладь спинку ежа';
 clearInterval(clock);draw();clock=setInterval(function(){left=Math.max(0,deadline-Date.now());draw();if(!left)clearInterval(clock);},250);
}
function ask(action){
 busy=true;
 TelegramWidget.request('hg:'+action+':'+token).then(function(answer){busy=false;try{show(JSON.parse(answer.result));}catch(e){note.textContent='Ёж потерял ответ. Погладь ещё раз — повторной награды не будет.';}},function(e){busy=false;note.textContent='Связь с ежом: '+e.code+'. Нажми ещё раз.';});
}
pet.onclick=function(){
 if(busy)return;
 if(!playing){ask('s');return;}
 if(left<=0){ask('f');return;}
 pets++;note.textContent=pets%2?'Фыр-фыр! Кажется, ему нравится.':'Осторожно, не против колючек!';
};
if(TelegramWidget.isForward||TelegramWidget.isPreview){pet.disabled=true;note.textContent='Вызови /senseidaily у бота для своей попытки.';}
TelegramWidget.ready();
</script></body></html>'''
