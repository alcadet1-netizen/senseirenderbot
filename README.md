# �� 🥋 SENSEI ULTIMATE 2.1
Эпический Telegram-бот для повышения активности в чате.

## �� 🚀 Быстрый старт

### 1. Клонировать репозиторий
```bash
git clone https://github.com/alcadet1-netizen/senseirenderbot.git
cd senseirenderbot
```

### 2. Установка зависимостей
```bash
# Рекомендуется использовать виртуальное окружение
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.\.venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### 3. Настройка окружения
Скопируйте пример конфигурации и заполните необходимые значения:
```bash
cp .env.example .env
```
Отредактируй `.env`, указав:
- `BOT_TOKEN` – токен вашего Telegram-бота (получить у @BotFather)
- `MONGO_URI` – строка подключения к MongoDB (по умолчанию `mongodb://localhost:27017/sensei`)
- При необходимости: `HF_TOKEN` – токен Hugging Face для генерации изображений (опционально)
- Другие API‑ключи (если используете внешние сервисы)

### 4. Запуск бота
```bash
# Если используется docker-compose (рекомендовано для разработки):
docker-compose up -d

# Или直接 запуск:
python -m src.bot.main
```

Бот начнетpolling и будет готов к работе.

## �� 📁 Структура проекта
```
senseirenderbot/
├── src/                     # Исходный код
│   ├── bot/                 # Основной код бота (aiogram)
│   │   ├── handlers/        # Обработчики команд и событий
│   │   ├── middlewares/     # Пользовательские middleware
│   │   ├── states/          # FSM состояния
│   │   ├── keyboards/       # Клавиатуры
│   │   ├── db.py            # Инициализация MongoDB
│   │   └── main.py          # Точка входа
│   ├── core/                # Ядро: конфигурация, DI‑контейнер, провайдеры
│   ├── infra/               # Инфраструктурные слои (MongoDB, Redis‑адаптер)
│   ├── services/            # Бизнес‑логика (игры, экономика и т.д.)
│   ├── domain/              # Доменные модели и ресурсы
│   └── texts/               # Локализуемые строки и фразы
├── scripts/                 # Вспомогательные скрипты (seed, очистка и т.д.)
├── .env.example             # Пример файла переменных окружения
├── docker-compose.yml       # Конфигурация для запуска MongoDB (и optionally других сервисов)
├── Dockerfile               # Официальный образ для production
├── README.md                # Этот файл
├── requirements.txt         # Зависимости Python
�└── .github/
    └── workflows/
        └── ci.yml           # GitHub Actions CI (запуск тестов при push)
```

## �� 🛠��️ Доступные скрипты
- `scripts/seed_data.py` – заполняет базу начальными данными (пользователи, достижения и т.п.).
- `scripts/verify_deletion.py` – проверяет корректность удаления пользователей.
- `scripts/delete_users.py` – удаляет тестовых пользователей (по необходимости).

## �� 🧪 Тесты
Запуск тестов:
```bash
pytest
```
CI workflow (`.github/workflows/ci.yml`) автоматически запушит тесты при каждом push в `main`.

## �� 🐳 Docker
Для production рекомендуется собрать образ:
```bash
docker build -t sensei-bot:latest .
```
И запустить с подключением к вашей MongoDB:
```bash
docker run -d --name sensei-bot \
  --env-file .env \
  sensei-bot:latest
```
Если используете `docker-compose.yml`, достаточно:
```bash
docker-compose up -d
```
Он поднимет контейнер с ботом и сервис MongoDB.

## �� 📦 Распространяемый архив
Для удобного распространения подготовлен архив `sensei-distributive.zip` (не включён в репозиторий, так как представляет собой собранный дистрибутив). Вы можете создать его сами:
```bash
git archive --format=zip --output=sensei-distributive.zip HEAD
```

## �� 📜 Лицензия
Проект распространяется под лицензией MIT – см. файл `LICENSE` (если присутствует).

## �� 🙏 Благодарности
- [aiogram](https://docs.aiogram.dev/) – мощная фреймворк для Telegram‑ботов.
- [MongoDB](https://www.mongodb.com/) – NoSQL‑база данных.
- [Hugging Face Inference API](https://huggingface.co/inference-api) – генерация изображений.
- Весь открытый‑сообщество, чьи инструменты и библиотеки делают разработку проще и приятнее.

---

_Если у вас возникли вопросы или предложения – откройте Issue или Pull Request. Удачной разработки и пусть ваш чат будет полон активности!_