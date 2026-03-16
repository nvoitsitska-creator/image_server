"""
Сервер зображень — Python HTTP бекенд.
Обробляє завантаження зображень, валідацію та логування.
"""

import cgi
import io
import json
import logging
import mimetypes
import os
import uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from PIL import Image

# Конфігурація
HOST = '0.0.0.0'
PORT = 8000
IMAGES_DIR = os.environ.get('IMAGES_DIR', '/app/images')
LOGS_DIR = os.environ.get('LOGS_DIR', '/app/logs')
STATIC_DIR = os.environ.get('STATIC_DIR', '/app/static')
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif'}

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


class ImageServerHandler(BaseHTTPRequestHandler):
    """HTTP обробник запитів для сервера зображень."""

    def do_GET(self):
        """Обробка GET запитів."""
        path = self.path.split('?')[0]

        if path == '/' or path == '':
            self._serve_file(os.path.join(STATIC_DIR, 'index.html'), 'text/html')
        elif path == '/upload':
            self._serve_file(os.path.join(STATIC_DIR, 'form', 'upload.html'), 'text/html')
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
        else:
            self._send_error(404, 'Маршрут не знайдено')

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
    server = ThreadingHTTPServer((HOST, PORT), ImageServerHandler)
    logger.info('Сервер запущено на %s:%d', HOST, PORT)
    print(f'Сервер запущено на http://{HOST}:{PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info('Сервер зупинено.')
        print('\nСервер зупинено.')
        server.server_close()


if __name__ == '__main__':
    main()
