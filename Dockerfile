FROM dockerhub.timeweb.cloud/library/python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Increase timeout and retries for apt
RUN echo "Acquire::http::Timeout \"60\";" > /etc/apt/apt.conf.d/99timeout && \
    echo "Acquire::Retries \"5\";" >> /etc/apt/apt.conf.d/99timeout

# Change mirror to yandex for faster download in RU region
RUN sed -i 's/deb.debian.org/mirror.yandex.ru/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirror.yandex.ru/g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    ffmpeg \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --default-timeout=1000

COPY . .

RUN chmod +x start.sh
RUN mkdir -p /app/src/infra/storage/ega

CMD ["./start.sh"]