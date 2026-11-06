'use strict';
const tg = window.Telegram?.WebApp;
const $ = id => document.getElementById(id);
const session = new URLSearchParams(location.search).get('session');
let active = false, finishing = false, deadline = 0, raf = 0, pets = 0, lastPet = 0;
const error = text => { $('error').textContent = text; $('error').hidden = false; };
async function api(action) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch('/miniapp/hedgehog/api/' + action, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({session, initData: tg.initData}), signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Ёж временно вне зоны ласки.');
    return data;
  } finally { clearTimeout(timer); }
}
function showResult(data) {
  active = false; cancelAnimationFrame(raf);
  $('clock').textContent = 'Готово'; $('timer').value = 0;
  const r = data.result;
  $('result-title').textContent = r.success ? 'Вы погладили ежа!' : 'Ёж включил кактус';
  $('result-message').textContent = r.message;
  $('rewards').replaceChildren();
  if (r.success) {
    for (const text of [`+${r.total_xp} XP`, `+${r.total_coins} монет`, `Серия: ${r.streak}`]) {
      const item = document.createElement('span'); item.textContent = text; $('rewards').append(item);
    }
    tg.HapticFeedback?.notificationOccurred('success');
  } else {
    const item = document.createElement('span'); item.textContent = 'Серия: 0 · Ничего не списано'; $('rewards').append(item);
    tg.HapticFeedback?.notificationOccurred('warning');
  }
  if (r.success && data.image) {
    $('reward-image').src = data.image; $('reward-image').hidden = false; $('verdict-icon').hidden = true;
    $('reward-image').onerror = () => { $('reward-image').hidden = true; $('verdict-icon').hidden = false; };
  }
  $('result').hidden = false; $('close').focus();
  $('retry').hidden = true;
}
function tick() {
  if (!active) return;
  const left = Math.max(0, deadline - performance.now());
  $('clock').textContent = `${Math.ceil(left / 1000)} сек`;
  $('timer').value = left;
  if (!left) { active = false; finish(); }
  else raf = requestAnimationFrame(tick);
}
function continueGame(data) {
  if (data.state === 'done') { showResult(data); return; }
  deadline = performance.now() + data.remaining_ms;
  active = true; $('play').hidden = true;
  $('status').textContent = 'Веди пальцем по спинке ежа';
  $('stage-label').textContent = 'Он уже почти доверяет тебе…';
  cancelAnimationFrame(raf); tick();
}
async function finish() {
  if (finishing) return;
  finishing = true; $('status').textContent = 'Ёж выносит колючий вердикт…';
  $('retry').hidden = true; $('error').hidden = true;
  try {
    const data = await api('finish');
    if (data.state === 'playing') continueGame(data);
    else showResult(data);
  } catch (e) {
    error(e.name === 'AbortError' ? 'Ёж задумался. Проверьте результат ещё раз — попытка не повторится.' : e.message);
    $('retry').hidden = false;
  } finally { finishing = false; }
}
$('play').onclick = async () => {
  if (!tg?.initData || !session) { error('Откройте эту игру кнопкой из /senseidaily в Telegram.'); return; }
  $('play').disabled = true; $('error').hidden = true;
  try { continueGame(await api('start')); }
  catch (e) { error(e.name === 'AbortError' ? 'Не удалось связаться с ежом. Попробуйте ещё раз.' : e.message); $('play').disabled = false; }
};
let touching = false;
function pet() {
  if (!active || performance.now() - lastPet < 260) return;
  lastPet = performance.now(); pets++;
  $('stage').classList.remove('petting');
  void $('stage').offsetWidth;
  $('stage').classList.add('petting');
  $('status').textContent = ['Тише, не против шерсти…', 'Фыр-фыр. Это хороший знак!', 'Ёж почти растаял от нежности'][Math.min(2, Math.floor(pets / 4))];
  tg?.HapticFeedback?.impactOccurred('soft');
}
$('stage').onpointerdown = e => { touching = true; $('stage').setPointerCapture(e.pointerId); pet(); };
$('stage').onpointermove = () => { if (touching) pet(); };
$('stage').onpointerup = $('stage').onpointercancel = () => { touching = false; };
$('retry').onclick = finish;
$('close').onclick = () => { tg?.close(); };
if (tg) { tg.ready(); tg.expand(); }
if (!tg?.initData || !session) { $('play').disabled = true; error('Эта мини-игра открывается кнопкой из /senseidaily в Telegram.'); }
