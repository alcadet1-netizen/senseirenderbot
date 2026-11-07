'use strict';
const tg = window.Telegram?.WebApp;
const $ = id => document.getElementById(id);
const session = new URLSearchParams(location.hash.slice(1)).get('session');
let loaded = false, ended = false, deadline = Infinity, frame = 0, raf = 0;
let pending = 0, confirmed = {taps: 0, extra_coins: 0}, failed = new Map();
const setError = message => { $('error').textContent = message; $('error').hidden = !message; };
const pose = n => { $('atlas').style.left = `${-(n % 4) * 100}%`; $('atlas').style.top = `${-Math.floor(n / 4) * 100}%`; };
function status() {
  $('status').textContent = pending ? `Подтверждаем поглаживания: ${pending}…` :
    ended ? 'Основная награда и подтверждённые добавки сохранены.' : 'Фыр-фыр! Каждый принятый тап — ещё +10% монет.';
  $('retry').hidden = pending > 0 || (!failed.size && !ended);
}
function finishVisual() {
  ended = true; cancelAnimationFrame(raf); pose(confirmed.taps ? 7 : 1);
  document.body.classList.add('ended'); $('ending').hidden = false;
  $('end-title').textContent = confirmed.taps ? 'Ёжик доволен!' : 'Ёжик отдыхает';
  $('clock').textContent = 'Готово'; $('progress').style.transform = 'scaleX(0)'; status();
}
function tick() {
  if (!loaded || ended) return;
  const left = Math.max(0, deadline - performance.now());
  $('clock').textContent = `${Math.ceil(left / 1000)} сек`;
  $('clock').parentElement.classList.toggle('urgent', left < 3000);
  $('progress').style.transform = `scaleX(${Math.min(1, left / 10000)})`;
  if (!left) finishVisual(); else raf = requestAnimationFrame(tick);
}
function apply(data) {
  loaded = true;
  // Late/out-of-order responses never renew the visual clock or roll counters back.
  deadline = Math.min(deadline, performance.now() + data.remaining_ms);
  if (data.taps >= confirmed.taps) confirmed = data;
  $('taps').textContent = confirmed.taps; $('percent').textContent = `+${confirmed.taps * 10}% монет`;
  $('coins').textContent = `+${confirmed.extra_coins}`;
  cancelAnimationFrame(raf);
  if (data.state === 'done' || performance.now() >= deadline) finishVisual();
  else if (!ended) tick();
  if (ended) pose(confirmed.taps ? 7 : 1);
  status();
}
async function api(action, requestId) {
  const began = performance.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(`/miniapp/daily-pet/api/${action}`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, signal: controller.signal,
      body: JSON.stringify({session, initData: tg.initData, ...(requestId ? {request_id: requestId} : {})}),
    });
    const data = await response.json();
    if (!response.ok) { const e = new Error(data.error || 'Нет ответа сервера.'); e.status = response.status; throw e; }
    // Conservative RTT subtraction: a slow response must not add visual time.
    data.remaining_ms = Math.max(0, data.remaining_ms - (performance.now() - began));
    return data;
  } finally { clearTimeout(timer); }
}
function effect(x, y) {
  const root = $('effects');
  for (let i = 0; i < 4; i++) {
    const el = document.createElement('span'); el.className = i ? 'particle' : 'ring';
    el.style.setProperty('--x', `${x}px`); el.style.setProperty('--y', `${y}px`);
    if (i) {
      el.textContent = i === 3 ? '✦' : '♥';
      el.style.setProperty('--color', i === 3 ? '#ffe194' : '#ff83b5');
      el.style.setProperty('--size', `${18 + Math.random() * 14}px`);
      el.style.setProperty('--dx', `${(Math.random() - .5) * 110}px`);
      el.style.setProperty('--dy', `${55 + Math.random() * 70}px`);
      el.style.setProperty('--rot', `${(Math.random() - .5) * 60}deg`);
    }
    root.append(el); el.addEventListener('animationend', () => el.remove(), {once: true});
    setTimeout(() => el.remove(), 850);
  }
}
function uuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return Array.from(crypto.getRandomValues(new Uint32Array(4)), n => n.toString(16).padStart(8, '0')).join('');
}
async function submit(id) {
  pending++; status();
  try { apply(await api('tap', id)); failed.delete(id); }
  catch (e) {
    // Retry ambiguous requests with EXACTLY the same ID, including after deadline.
    // Permanent/auth/rate-limit refusals are never blindly reissued.
    if (!e.status || e.status >= 500) failed.set(id, true);
    setError(e.name === 'AbortError' ? 'Ответ задерживается. «Обновить» безопасно проверит его.' : e.message);
  } finally { pending--; status(); }
}
function touch(event) {
  if (event.target.closest('[data-no-pet]') || !loaded || ended) return;
  if (performance.now() >= deadline) { finishVisual(); return; }
  frame = frame < 6 ? frame + 1 : 1; pose(frame);
  effect(event.clientX, event.clientY);
  try { tg.HapticFeedback?.impactOccurred('soft'); } catch (_) {}
  if (pending < 120) void submit(uuid());
}
document.addEventListener('pointerdown', touch);
$('stage').addEventListener('keydown', event => {
  if (event.key === ' ' || event.key === 'Enter') {
    event.preventDefault(); const r = $('stage').getBoundingClientRect();
    touch({target: $('stage'), clientX: r.left + r.width / 2, clientY: r.top + r.height * .65});
  }
});
$('close').onclick = () => tg?.close();
$('retry').onclick = async () => {
  if (pending) return; setError('');
  await Promise.all([...failed.keys()].map(submit));
  try { apply(await api('view')); } catch (e) { setError(e.message); }
};
if (tg) { tg.ready(); tg.expand(); try { tg.setHeaderColor('#173b25'); tg.setBackgroundColor('#173b25'); } catch (_) {} }
if (!tg?.initData || !session) {
  setError('Откройте игру кнопкой из личного сообщения бота внутри Telegram.');
  $('status').textContent = 'Нет авторизованной сессии.';
} else {
  api('view').then(data => { apply(data); frame = Math.min(confirmed.taps, 6); if (!ended) pose(frame); })
    .catch(e => { setError(e.message); $('retry').hidden = false; });
}
