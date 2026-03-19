# Етап 1: Збірка залежностей
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Етап 2: Фінальний образ
FROM python:3.12-slim

WORKDIR /app

# Копіюємо встановлені пакети
COPY --from=builder /install /usr/local

# Копіюємо код додатку
COPY app.py .
COPY static/ ./static/

# Створюємо директорії для даних
RUN mkdir -p /app/images /app/logs /app/backups

EXPOSE 8000

CMD ["python", "app.py"]
