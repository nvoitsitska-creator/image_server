# Покрокова інструкція для студентів

Ця інструкція допоможе вам зрозуміти, як побудований проект "Сервер зображень", та як його запустити і протестувати.

---

## 1. Передумови

Перед початком роботи переконайтеся, що у вас встановлено:

- **Docker** та **Docker Compose** — для контейнеризації
- **Python 3.12+** — для локальної розробки (опціонально)
- **Git** — для роботи з репозиторієм

### Перевірка встановлення

```bash
docker --version
docker compose version
python3 --version
git --version
```

---

## 2. Структура проекту

```
image_server/
├── app.py                # Python HTTP бекенд (основна логіка)
├── requirements.txt      # Залежності Python (Pillow)
├── Dockerfile            # Інструкція для створення Docker-образу
├── compose.yaml          # Конфігурація Docker Compose (2 сервіси)
├── nginx.conf            # Конфігурація веб-сервера Nginx
├── static/               # Фронтенд (HTML, CSS, JS)
│   ├── index.html        # Головна сторінка
│   ├── form/
│   │   ├── upload.html   # Сторінка завантаження
│   │   └── images.html   # Сторінка списку зображень
│   └── image-uploader/
│       ├── css/          # Стилі (reset.css, style.css)
│       ├── js/           # Скрипти (index.js, upload.js, images.js)
│       └── img/          # Зображення для дизайну
├── images/               # Папка для завантажених зображень (Docker volume)
└── logs/                 # Папка для логів (Docker volume)
```

---

## 3. Розробка бекенду (app.py) — крок за кроком

### 3.1. Імпорти та конфігурація

```python
import cgi          # Для розбору multipart/form-data
import json         # Для JSON відповідей
import logging      # Для логування
import os           # Для роботи з файловою системою
import uuid         # Для генерації унікальних імен файлів
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
```

**Чому `ThreadingHTTPServer`?** Звичайний `HTTPServer` обробляє лише один запит за раз. `ThreadingHTTPServer` створює окремий потік для кожного запиту, що дозволяє обробляти до 10 одночасних з'єднань.

### 3.2. Константи

```python
HOST = '0.0.0.0'           # Слухаємо на всіх інтерфейсах
PORT = 8000                 # Порт сервера
IMAGES_DIR = '/app/images'  # Де зберігаються зображення
LOGS_DIR = '/app/logs'      # Де зберігаються логи
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ у байтах
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}
```

### 3.3. Налаштування логування

```python
logger = logging.getLogger('image_server')
logger.setLevel(logging.INFO)

# Запис логів у файл
file_handler = logging.FileHandler(
    os.path.join(LOGS_DIR, 'app.log'),
    encoding='utf-8'
)
formatter = logging.Formatter(
    '[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
```

Це створює логи у форматі: `[2025-01-24 14:00:00] Успіх: зображення img1.jpg завантажено.`

### 3.4. Обробник HTTP запитів

Ми створюємо клас `ImageServerHandler`, який наслідує `BaseHTTPRequestHandler`. Він має два основних методи:

- `do_GET()` — обробляє GET запити (сторінки, статичні файли)
- `do_POST()` — обробляє POST запити (завантаження файлів)

### 3.5. Маршрутизація (Routing)

```python
def do_GET(self):
    path = self.path.split('?')[0]  # Відкидаємо query параметри

    if path == '/':
        # Головна сторінка
        self._serve_file('static/index.html', 'text/html')
    elif path == '/upload':
        # Сторінка завантаження
        self._serve_file('static/form/upload.html', 'text/html')
    elif path.startswith('/image-uploader/'):
        # CSS, JS, зображення дизайну
        self._serve_static(file_path)
    elif path.startswith('/images/'):
        # Завантажені зображення
        self._serve_static(file_path)
```

### 3.6. Логіка завантаження файлу

Послідовність обробки POST запиту на `/upload`:

1. **Перевірка Content-Type** — чи це `multipart/form-data`?
2. **Перевірка Content-Length** — чи не перевищує 5 МБ?
3. **Розбір форми** — за допомогою `cgi.FieldStorage`
4. **Перевірка розширення** — чи є файл зображенням (.jpg, .png, .gif)?
5. **Зчитування даних** — читаємо вміст файлу
6. **Перевірка розміру** — перевіряємо фактичний розмір
7. **Генерація імені** — `uuid.uuid4().hex` + розширення (наприклад, `a1b2c3d4.jpg`)
8. **Збереження** — записуємо файл у папку `/app/images/`
9. **Логування** — записуємо результат у лог
10. **Відповідь** — повертаємо JSON з URL зображення

### 3.7. Безпека

- **Path traversal захист** — перевіряємо, що шлях файлу не виходить за межі дозволених директорій:
  ```python
  real_path = os.path.realpath(file_path)
  if not real_path.startswith(STATIC_DIR):
      self._send_error(403, 'Доступ заборонено')
  ```
- **Валідація розширення** — приймаємо тільки дозволені формати
- **Обмеження розміру** — перевіряємо і Content-Length, і фактичний розмір
- **Унікальні імена** — UUID запобігає конфліктам імен та перезапису файлів

---

## 4. Конфігурація Nginx (nginx.conf)

```nginx
server {
    listen 80;                    # Nginx слухає на порту 80
    client_max_body_size 5M;      # Обмеження розміру запиту

    location /images/ {
        alias /images/;           # Роздача зображень напряму з файлової системи
    }

    location / {
        proxy_pass http://app:8000;  # Все інше — проксі на Python бекенд
    }
}
```

**Чому Nginx?** Nginx набагато ефективніше роздає статичні файли (зображення), ніж Python. Python обробляє логіку (завантаження, валідацію), а Nginx — швидку роздачу файлів.

**Як це працює:**
1. Запит на `http://localhost:8080/images/photo.jpg` → Nginx віддає файл напряму
2. Запит на `http://localhost:8080/upload` → Nginx перенаправляє на Python бекенд

---

## 5. Docker та Docker Compose

### 5.1. Dockerfile (Multi-stage build)

```dockerfile
# Етап 1: Збірка — встановлюємо залежності
FROM python:3.12-slim AS builder
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# Етап 2: Фінальний образ — тільки потрібне
FROM python:3.12-slim
COPY --from=builder /install /usr/local
COPY app.py .
COPY static/ ./static/
```

**Чому multi-stage?** Перший етап містить інструменти для збірки (pip, компілятори). Другий етап бере тільки результат — готові пакети. Це зменшує розмір фінального образу.

### 5.2. Docker Compose (compose.yaml)

```yaml
services:
  app:              # Python бекенд
    build: .
    ports:
      - "8000:8000"
    volumes:
      - images_data:/app/images    # Том для зображень
      - logs_data:/app/logs        # Том для логів

  nginx:            # Nginx сервер
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - images_data:/images:ro     # Той самий том (тільки читання)
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro

volumes:
  images_data:      # Спільний том для зображень
  logs_data:        # Том для логів
```

**Ключовий момент:** `images_data` — це спільний том. Python бекенд записує туди зображення, а Nginx їх читає. Це дозволяє двом контейнерам працювати з одними й тими ж файлами.

---

## 6. Запуск та тестування

### 6.1. Запуск проекту

```bash
# Збірка та запуск обох контейнерів
docker compose up --build
```

Ви побачите логи обох сервісів у терміналі.

### 6.2. Тестування через браузер

1. Відкрийте **http://localhost:8080** — головна сторінка
2. Натисніть "Tail-ent Showcase" — перейдіть на сторінку завантаження
3. Перетягніть зображення в зону завантаження або натисніть "Browse your file"
4. Після завантаження скопіюйте URL та відкрийте в новій вкладці

### 6.3. Тестування через curl

```bash
# Завантаження зображення
curl -X POST -F "file=@photo.jpg" http://localhost:8080/upload

# Очікувана відповідь:
# {"success": true, "filename": "a1b2c3d4.jpg", "url": "/images/a1b2c3d4.jpg"}

# Перегляд зображення
curl -I http://localhost:8080/images/a1b2c3d4.jpg

# Тест помилки — неправильний формат
curl -X POST -F "file=@document.pdf" http://localhost:8080/upload

# Тест помилки — завеликий файл (>5MB)
curl -X POST -F "file=@large_image.png" http://localhost:8080/upload
```

### 6.4. Перевірка логів

```bash
# Подивитися логи бекенду
docker compose exec app cat /app/logs/app.log
```

Очікуваний формат:
```
[2025-01-24 14:00:00] Сервер запущено на 0.0.0.0:8000
[2025-01-24 14:00:05] Успіх: зображення photo.jpg завантажено.
[2025-01-24 14:00:10] Помилка: непідтримуваний формат файлу (document.pdf).
```

### 6.5. Зупинка проекту

```bash
# Зупинити контейнери (дані збережуться у volumes)
docker compose down

# Зупинити та видалити volumes (УВАГА: всі дані будуть втрачені!)
docker compose down -v
```

---

## 7. Часті проблеми та їх вирішення

### Порт зайнятий
```
Error: port 8080 is already in use
```
**Рішення:** Змініть порт у `compose.yaml`, наприклад `"8081:80"`

### Помилка прав доступу до volumes
```
PermissionError: [Errno 13] Permission denied
```
**Рішення:** Переконайтеся, що директорії `images/` та `logs/` створені та мають правильні дозволи

### Nginx повертає 502 Bad Gateway
**Причина:** Python бекенд ще не встиг запуститися
**Рішення:** Зачекайте кілька секунд або перезапустіть: `docker compose restart`

### Зображення не відображається
**Перевірте:**
1. Чи файл дійсно завантажився: `docker compose exec app ls /app/images/`
2. Чи Nginx бачить файл: `docker compose exec nginx ls /images/`
3. Чи правильний URL: `/images/filename.jpg`

---

## 8. Довідка API

### POST /upload

Завантаження зображення на сервер.

**Запит:**
- Content-Type: `multipart/form-data`
- Поле: `file` — файл зображення

**Обмеження:**
- Формати: `.jpg`, `.jpeg`, `.png`, `.gif`
- Максимальний розмір: 5 МБ

**Успішна відповідь (200):**
```json
{
    "success": true,
    "filename": "a1b2c3d4e5f6.jpg",
    "original_name": "photo.jpg",
    "url": "/images/a1b2c3d4e5f6.jpg"
}
```

**Помилка (400):**
```json
{
    "success": false,
    "error": "Непідтримуваний формат файлу. Дозволені: .jpg, .jpeg, .png, .gif"
}
```

### GET /images/{filename}

Перегляд завантаженого зображення. Обслуговується Nginx напряму.

### GET /

Головна сторінка з вітанням та посиланнями.

### GET /upload

Сторінка з формою для завантаження зображень.
