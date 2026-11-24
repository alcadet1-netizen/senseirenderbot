// Админ-панель: добавление канала в задания. Статические проверки фронтенда.
//
// Браузера в CI нет, поэтому проверяем то, что реально ломалось: админ
// отправлял форму, сервер отвечал 409, а в панели появлялось лишь «не
// получилось». Теперь подсказка разбирает @username до отправки, а на отказ
// «такое задание уже есть» панель предлагает открыть существующее.
const assert = require('node:assert/strict');
const fs = require('node:fs');

const html = fs.readFileSync('src/web/dojo/index.html', 'utf8');
const js = fs.readFileSync('src/web/dojo/miner.js', 'utf8');
const css = fs.readFileSync('src/web/dojo/style.css', 'utf8');

// 1. Подсказка под полем существует и её id совпадает с тем, что ищет JS.
assert.match(html, /id="admin-target-hint"/, 'нет элемента подсказки');
assert.match(js, /\$\("admin-target-hint"\)/, 'JS не обновляет подсказку');

// 2. Ввод проверяется до отправки: та же регулярка, что и на сервере
//    (5–32 символа, латиница/цифры/_, начинается с буквы).
assert.match(js, /\[A-Za-z\]\[A-Za-z0-9_\]\{4,31\}/, 'нет локальной проверки username');
assert.match(js, /addEventListener\("input", adminTargetHint\)/, 'подсказка не реагирует на ввод');

// 3. Лукапы t.me и @ снимаются — админ может вставить ссылку как есть.
assert.match(js, /replace\(\/\^t\\\.me\\\/\/i, ""\)/, 'ссылка t.me не нормализуется в UI');

// 4. 409 с task_exists даёт кнопку перехода к существующему заданию,
//    а не тупиковое сообщение.
assert.match(js, /error\.code === "task_exists"/, 'нет обработки кода task_exists');
assert.match(js, /"Открыть его"/, 'нет кнопки перехода к существующему заданию');
assert.match(js, /adminTasks\.find\(item => item\.slug === error\.slug\)/, 'не ищет задание по slug');

// 5. api() прокидывает code/slug из тела 409 — иначе UI нечего показать.
assert.match(js, /error\.code = data\.code \|\| ""/, 'api() теряет code');
assert.match(js, /error\.slug = data\.slug \|\| ""/, 'api() теряет slug');

// 6. Кнопка внутри сообщения должна выглядеть кнопкой, а не текстом.
assert.match(css, /\.admin-message-action\s*\{/, 'нет стиля для кнопки в сообщении');
assert.match(css, /\.admin-hint\.error\s*\{/, 'ошибка подсказки не выделяется цветом');

// 7. Форма не создаёт второй таск на тот же канал: ключ формы остаётся
//    прежним при редактировании, поэтому повторная отправка — ретрай.
assert.match(js, /adminCreateKey = task \? "" : crypto\.randomUUID\(\)/,
  'при редактировании ключ создания должен сбрасываться');

console.log('dojo_admin_tasks: ok');
