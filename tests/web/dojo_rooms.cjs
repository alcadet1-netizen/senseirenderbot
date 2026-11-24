// Комнаты и отправка вызова: статические проверки фронтенда.
//
// Браузера в CI нет, поэтому проверяем то, что реально ломалось и что можно
// доказать по исходникам: мини-апп больше не закрывается при приглашении в
// чат, список комнат не пересоздаёт кнопки на каждом тике и анимация боя
// не анимирует дорогие свойства.
const assert = require('node:assert/strict');
const fs = require('node:fs');

const html = fs.readFileSync('src/web/dojo/index.html', 'utf8');
const js = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const css = fs.readFileSync('src/web/dojo/style.css', 'utf8');

// 1. «В группу» больше не закрывает мини-апп.
// Упоминание в комментарии допустимо — проверяем именно вызов.
assert.doesNotMatch(js, /tg\.switchInlineQuery\(/, 'switchInlineQuery закрывает мини-апп');
assert.match(js, /api\("vs_publish",\s*\{bet,\s*chat: chatId\}\)/, 'вызов должен уходить через бота');

// 2. Панель выбора группы существует и её id совпадает с тем, что ищет JS.
assert.match(html, /id="vs-chat-panel"/);
assert.match(js, /\$\("vs-chat-panel"\)/);

// 3. Комнаты: элементы в HTML и обработчики в JS.
for (const id of ['vs-rooms', 'vs-room-create', 'vs-room-list', 'vs-room-bet']) {
  assert.match(html, new RegExp(`id="${id}"`), `нет #${id}`);
}
for (const action of ['vs_rooms', 'vs_room_create', 'vs_room_join', 'vs_room_close']) {
  assert.match(js, new RegExp(`"${action}"`), `JS не вызывает ${action}`);
}

// 4. Список комнат не перестраивается, если данные не изменились:
//    иначе кнопки мигают каждые 4 секунды.
assert.match(js, /list\.dataset\.key === key\) return;/, 'нет защиты от перерисовки');

// 5. Никакого принудительного reflow перед ударом.
assert.doesNotMatch(js, /void comic\.offsetWidth/, 'reflow перед ударом вызывает рывок');

// 6. Анимация боя не трогает filter и box-shadow в ключевых кадрах.
const combatKeyframes = css.split('SMOOTH COMBAT')[1] || '';
assert.ok(combatKeyframes.length > 500, 'нет плавного слоя боя');
assert.doesNotMatch(combatKeyframes, /@keyframes[^{]*\{[^}]*filter\s*:/, 'filter в анимации = перерисовка');
assert.doesNotMatch(combatKeyframes, /@keyframes[^{]*\{[^}]*box-shadow\s*:/, 'box-shadow в анимации = мерцание');

// 7. Пульсация box-shadow у кнопки «В бой» убрана.
assert.doesNotMatch(css, /animation:\s*vs-commit-pulse/, 'пульсация box-shadow мигает');

// 8. Фигуры идут на собственном слое.
assert.match(css, /\.vs-fighter\s*\{[^}]*will-change:\s*transform/);

// 9. На узких экранах тяжёлые слои убираются.
assert.match(css, /@media \(max-width: 480px\), \(update: slow\)/);

// 10. Ставка комнаты берётся из поля ввода, а не зашита числом.
assert.match(js, /function roomBet\(\)/);
assert.match(js, /Number\(\$\("vs-bet"\)\?\.value\)/);

console.log('Rooms + chat share + smooth combat: static checks passed.');
