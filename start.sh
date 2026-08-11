#!/bin/bash
set -e

# Применяем миграции
echo "🔄 Running database migrations..."
python -m alembic upgrade head

# Запускаем бота
echo "🚀 Starting bot..."
python -m src.main
