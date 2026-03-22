"""
Сервер зображень — Python HTTP бекенд.
Обробляє завантаження зображень, валідацію та логування.
"""

import cgi
import html
import io
import json
import logging
import mimetypes
import os
import time
import uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import psycopg2
from PIL import Image

# Конфігурація
HOST = '0.0.0.0'
PORT = 8000
IMAGES_DIR = os.environ.get('IMAGES_DIR', '/app/images')
LOGS_DIR = os.environ.get('LOGS_DIR', '/app/logs')
STATIC_DIR = os.environ.get('STATIC_DIR', '/app/static')
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}

# Конфігурація БД
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_NAME', 'images_db')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')

ITEMS_PER_PAGE = 10

# Налаштування логування
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

logger = logging.getLogger('image_server')
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'app.log'), encoding='utf-8')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Глобальне з'єднання з БД
_db_connection = None


def get_db_connection():
    """Отримати з'єднання з БД (з кешуванням та перепідключенням)."""
    global _db_connection
    if _db_connection is None or _db_connection.closed:
        _db_connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        _db_connection.autocommit = False
    return _db_connection


def init_db():
    """Ініціалізація таблиці в БД з повторними спробами."""
    for attempt in range(1, 6):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    original_name VARCHAR(255) NOT NULL,
                    size INTEGER NOT NULL,
                    file_type VARCHAR(10) NOT NULL,
                    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            cur.close()
            logger.info('Таблицю images ініціалізовано.')
            return
        except Exception as e:
            logger.info('Спроба %d підключення до БД не вдалася: %s', attempt, str(e))
            if attempt < 5:
                time.sleep(2)
            else:
                raise


def close_db():
    """Закрити з'єднання з БД."""
    global _db_connection
    if _db_connection and not _db_connection.closed:
        _db_connection.close()
        logger.info("З'єднання з БД закрито.")


class ImageServerHandler(BaseHTTPRequestHandler):
    """HTTP обробник запитів для сервера зображень."""

    def do_GET(self):
        """Обробка GET запитів."""
        path = self.path.split('?')[0]

        if path == '/' or path == '':
            self.send_response(302)
            self.send_header('Location', '/upload')
            self.end_headers()
        elif path == '/upload':
            self._serve_file(os.path.join(STATIC_DIR, 'form', 'upload.html'), 'text/html')
        elif path == '/images-list':
            self._handle_images_list()
        elif path.startswith('/image-uploader/'):
            file_path = os.path.join(STATIC_DIR, path.lstrip('/'))
            self._serve_static(file_path)
        elif path.startswith('/form/'):
            file_path = os.path.join(STATIC_DIR, path.lstrip('/'))
            self._serve_static(file_path)
        elif path.startswith('/images/'):
            file_path = os.path.join(IMAGES_DIR, os.path.basename(path))
            self._serve_static(file_path)
        else:
            self._send_error(404, 'Сторінку не знайдено')

    def do_POST(self):
        """Обробка POST запитів."""
        path = self.path.split('?')[0]

        if path == '/upload':
            self._handle_upload()
        elif path.startswith('/delete/'):
            self._handle_delete_by_id(path)
        else:
            self._send_error(404, 'Маршрут не знайдено')

    def do_DELETE(self):
        """Обробка DELETE запитів."""
        path = self.path.split('?')[0]

        if path.startswith('/images/'):
            self._handle_delete(path)
        else:
            self._send_error(404, 'Маршрут не знайдено')

    def _handle_delete(self, path):
        """Видалення зображення з сервера."""
        filename = os.path.basename(path)
        file_path = os.path.join(IMAGES_DIR, filename)
        real_path = os.path.realpath(file_path)

        if not real_path.startswith(os.path.realpath(IMAGES_DIR)):
            self._send_error(403, 'Доступ заборонено')
            return

        if not os.path.isfile(real_path):
            self._send_json(404, {'success': False, 'error': 'Файл не знайдено'})
            return

        try:
            os.remove(real_path)
            logger.info('Видалено зображення: %s', filename)

            try:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM images WHERE filename = %s", (filename,))
                conn.commit()
                cur.close()
            except Exception as e:
                logger.info('Помилка видалення з БД: %s', str(e))

            self._send_json(200, {'success': True})
        except OSError as e:
            logger.info('Помилка видалення файлу: %s', str(e))
            self._send_json(500, {'success': False, 'error': 'Не вдалося видалити файл'})

    def _handle_delete_by_id(self, path):
        """Видалення зображення за ID з БД."""
        id_str = path.split('/delete/')[-1]
        try:
            image_id = int(id_str)
        except ValueError:
            self._send_error(400, 'Невірний ID')
            return

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT filename FROM images WHERE id = %s", (image_id,))
            row = cur.fetchone()

            if not row:
                cur.close()
                self._send_error(404, 'Зображення не знайдено')
                return

            filename = row[0]
            cur.execute("DELETE FROM images WHERE id = %s", (image_id,))
            conn.commit()
            cur.close()

            file_path = os.path.join(IMAGES_DIR, filename)
            try:
                os.remove(file_path)
            except OSError as e:
                logger.info('Файл не знайдено на диску: %s', str(e))

            logger.info('Видалено зображення (id=%d): %s', image_id, filename)

            self.send_response(303)
            self.send_header('Location', '/images-list')
            self.end_headers()

        except Exception as e:
            logger.info('Помилка видалення за ID: %s', str(e))
            try:
                conn.rollback()
            except Exception:
                pass
            self._send_error(500, 'Помилка видалення')

    def _handle_images_list(self):
        """Відображення списку зображень з БД з пагінацією."""
        query_string = urlparse(self.path).query
        params = parse_qs(query_string)
        try:
            page = int(params.get('page', ['1'])[0])
            if page < 1:
                page = 1
        except ValueError:
            page = 1

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM images")
            total = cur.fetchone()[0]

            total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            if page > total_pages:
                page = total_pages

            offset = (page - 1) * ITEMS_PER_PAGE
            cur.execute(
                "SELECT id, filename, original_name, size, file_type, upload_time "
                "FROM images ORDER BY upload_time DESC LIMIT %s OFFSET %s",
                (ITEMS_PER_PAGE, offset)
            )
            rows = cur.fetchall()
            cur.close()

        except Exception as e:
            logger.info('Помилка отримання списку зображень: %s', str(e))
            self._send_error(500, 'Помилка бази даних')
            return

        # Формуємо рядки таблиці
        if rows:
            table_rows = ""
            for row in rows:
                img_id, filename, original_name, size, file_type, upload_time = row
                size_kb = f"{size / 1024:.1f}"
                upload_str = upload_time.strftime('%Y-%m-%d %H:%M:%S')
                table_rows += f"""
                <tr>
                    <td><a href="/images/{html.escape(filename)}" target="_blank">{html.escape(filename)}</a></td>
                    <td>{html.escape(original_name)}</td>
                    <td>{size_kb}</td>
                    <td>{html.escape(upload_str)}</td>
                    <td>{html.escape(file_type)}</td>
                    <td>
                        <form method="POST" action="/delete/{img_id}" style="display:inline;">
                            <button type="submit" class="delete-btn">Видалити</button>
                        </form>
                    </td>
                </tr>"""
            table_content = f"""
            <table>
                <thead>
                    <tr>
                        <th>Назва файлу</th>
                        <th>Оригінальна назва</th>
                        <th>Розмір (КБ)</th>
                        <th>Дата завантаження</th>
                        <th>Тип файлу</th>
                        <th>Дія</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>"""
        else:
            table_content = '<p class="empty">Немає завантажених зображень</p>'

        # Пагінація
        prev_disabled = 'disabled' if page <= 1 else ''
        next_disabled = 'disabled' if page >= total_pages else ''
        pagination = f"""
        <div class="pagination">
            <a href="/images-list?page={page - 1}" class="page-btn {prev_disabled}">Попередня сторінка</a>
            <span>Сторінка {page} з {total_pages}</span>
            <a href="/images-list?page={page + 1}" class="page-btn {next_disabled}">Наступна сторінка</a>
        </div>"""

        page_html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Список зображень</title>
    <link rel="stylesheet" href="/image-uploader/css/reset.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/image-uploader/css/style.css">
    <style>
        body {{
            background-color: #151515;
            color: #ffffff;
            font-family: 'Inter', sans-serif;
            padding: 40px 20px;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 30px;
            font-size: 2rem;
        }}
        table {{
            width: 100%;
            max-width: 1100px;
            margin: 0 auto 30px;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #333;
        }}
        th {{
            background-color: #222;
            color: #aaa;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.8rem;
        }}
        td a {{
            color: #6ea8fe;
            text-decoration: none;
        }}
        td a:hover {{
            text-decoration: underline;
        }}
        .delete-btn {{
            background-color: #dc3545;
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85rem;
        }}
        .delete-btn:hover {{
            background-color: #bb2d3b;
        }}
        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 20px;
            margin-top: 20px;
        }}
        .page-btn {{
            background-color: #333;
            color: #fff;
            padding: 8px 18px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 0.9rem;
        }}
        .page-btn:hover:not(.disabled) {{
            background-color: #555;
        }}
        .page-btn.disabled {{
            opacity: 0.4;
            pointer-events: none;
        }}
        .empty {{
            text-align: center;
            color: #888;
            font-size: 1.2rem;
            margin-top: 60px;
        }}
        .back-link {{
            display: block;
            text-align: center;
            margin-top: 30px;
            color: #6ea8fe;
            text-decoration: none;
            font-size: 0.95rem;
        }}
        .back-link:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <h1>Список зображень</h1>
    {table_content}
    {pagination}
    <a href="/upload" class="back-link">← Завантажити зображення</a>
</body>
</html>"""

        data = page_html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_upload(self):
        """Обробка завантаження зображення."""
        content_type = self.headers.get('Content-Type', '')

        if 'multipart/form-data' not in content_type:
            logger.info('Помилка: невірний Content-Type (%s).', content_type)
            self._send_json(400, {
                'success': False,
                'error': 'Content-Type повинен бути multipart/form-data'
            })
            return

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > MAX_FILE_SIZE:
            logger.info('Помилка: файл занадто великий (%d байт).', content_length)
            self._send_json(400, {
                'success': False,
                'error': f'Файл занадто великий. Максимальний розмір: 5 МБ'
            })
            return

        try:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': content_type,
                }
            )
        except Exception as e:
            logger.info('Помилка: не вдалося розібрати форму (%s).', str(e))
            self._send_json(400, {
                'success': False,
                'error': 'Не вдалося розібрати дані форми'
            })
            return

        file_item = form['file'] if 'file' in form else None

        if file_item is None or not file_item.filename:
            logger.info('Помилка: файл не надано.')
            self._send_json(400, {
                'success': False,
                'error': 'Файл не надано'
            })
            return

        original_filename = os.path.basename(file_item.filename)
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()

        if ext not in ALLOWED_EXTENSIONS:
            logger.info('Помилка: непідтримуваний формат файлу (%s).', original_filename)
            self._send_json(400, {
                'success': False,
                'error': f'Непідтримуваний формат файлу. Дозволені: {", ".join(ALLOWED_EXTENSIONS)}'
            })
            return

        file_data = file_item.file.read()

        try:
            img = Image.open(io.BytesIO(file_data))
            img.verify()
        except Exception:
            logger.info('Помилка: файл не є дійсним зображенням (%s).', original_filename)
            self._send_json(400, {
                'success': False,
                'error': 'Файл не є дійсним зображенням'
            })
            return

        if len(file_data) > MAX_FILE_SIZE:
            logger.info('Помилка: файл занадто великий (%d байт).', len(file_data))
            self._send_json(400, {
                'success': False,
                'error': 'Файл занадто великий. Максимальний розмір: 5 МБ'
            })
            return

        unique_filename = uuid.uuid4().hex + ext
        save_path = os.path.join(IMAGES_DIR, unique_filename)

        try:
            with open(save_path, 'wb') as f:
                f.write(file_data)
        except OSError as e:
            logger.info('Помилка: не вдалося зберегти файл (%s).', str(e))
            self._send_json(500, {
                'success': False,
                'error': 'Не вдалося зберегти файл'
            })
            return

        # Зберігаємо метадані в БД
        file_type = ext.lstrip('.')
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO images (filename, original_name, size, file_type) VALUES (%s, %s, %s, %s)",
                (unique_filename, original_filename, len(file_data), file_type)
            )
            conn.commit()
            cur.close()
            logger.info('Метадані збережено в БД: %s', unique_filename)
        except Exception as e:
            logger.info('Помилка збереження в БД: %s', str(e))
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                os.remove(save_path)
            except OSError:
                pass
            self._send_json(500, {
                'success': False,
                'error': 'Не вдалося зберегти метадані в базу даних'
            })
            return

        image_url = f'/images/{unique_filename}'
        logger.info('Успіх: зображення %s завантажено.', original_filename)

        self._send_json(200, {
            'success': True,
            'filename': unique_filename,
            'original_name': original_filename,
            'url': image_url
        })

    def _serve_file(self, file_path, content_type):
        """Віддати файл з вказаним Content-Type."""
        real_path = os.path.realpath(file_path)
        if not os.path.isfile(real_path):
            self._send_error(404, 'Файл не знайдено')
            return

        with open(real_path, 'rb') as f:
            data = f.read()

        self.send_response(200)
        self.send_header('Content-Type', f'{content_type}; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, file_path):
        """Віддати статичний файл з автоматичним визначенням MIME-типу."""
        real_path = os.path.realpath(file_path)

        # Захист від path traversal
        allowed_dirs = [os.path.realpath(STATIC_DIR), os.path.realpath(IMAGES_DIR)]
        if not any(real_path.startswith(d) for d in allowed_dirs):
            self._send_error(403, 'Доступ заборонено')
            return

        if not os.path.isfile(real_path):
            self._send_error(404, 'Файл не знайдено')
            return

        mime_type, _ = mimetypes.guess_type(real_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        with open(real_path, 'rb') as f:
            data = f.read()

        self.send_response(200)
        self.send_header('Content-Type', mime_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, status_code, data):
        """Відправити JSON відповідь."""
        response = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _send_error(self, status_code, message):
        """Відправити помилку."""
        response = f'<html><body><h1>{status_code}</h1><p>{message}</p></body></html>'
        data = response.encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        """Перевизначення стандартного логування."""
        pass


def main():
    """Запуск сервера."""
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), ImageServerHandler)
    logger.info('Сервер запущено на %s:%d', HOST, PORT)
    print(f'Сервер запущено на http://{HOST}:{PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('Сервер зупинено.')
        print('\nСервер зупинено.')
        server.server_close()
        close_db()


if __name__ == '__main__':
    main()
