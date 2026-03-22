# Виправлення та рефакторинг

## Виправлення помилок

### 1. Кнопка "Copy" не копіює URL

**Проблема:** Кнопка "COPY" на сторінці завантаження використовувала `navigator.clipboard.writeText()`, який працює **тільки** в захищеному контексті (HTTPS або localhost). Оскільки проєкт запускається через Docker/Nginx на `http://localhost:8080`, браузер блокує доступ до Clipboard API і копіювання мовчки завершується помилкою.

**Файли:** `static/image-uploader/js/upload.js`, `static/image-uploader/js/common.js`

**Рішення:** Створено функцію `copyToClipboard(text)` у `common.js`, яка:
- Спочатку перевіряє, чи доступний `navigator.clipboard` та чи сторінка в захищеному контексті (`window.isSecureContext`)
- Якщо ні — використовує fallback: створює прихований `<textarea>`, вставляє текст і викликає `document.execCommand('copy')`
- Повертає `Promise`, що дозволяє використовувати `.then()` / `.catch()` незалежно від методу копіювання

```js
// Було (не працює через HTTP):
navigator.clipboard.writeText(textToCopy).then(...)

// Стало (працює в будь-якому контексті):
copyToClipboard(textToCopy).then(...)
```

---

### 2. Видалення зображень — файл не видаляється з сервера

**Проблема:** При натисканні кнопки видалення зображення видалялось лише з `localStorage` браузера. Файл залишався у папці `images/` на сервері, оскільки бекенд не мав ендпоінту для видалення файлів.

**Файли:** `app.py`, `static/image-uploader/js/images.js`

**Рішення:**

**Бекенд (`app.py`)** — додано метод `do_DELETE` та `_handle_delete`:
- Приймає DELETE-запити на `/images/<filename>`
- Перевіряє, що шлях не виходить за межі `IMAGES_DIR` (захист від path traversal)
- Видаляє файл з диска через `os.remove()`
- Логує результат операції
- Повертає JSON-відповідь з результатом

**Фронтенд (`images.js`)** — додано функцію `deleteFromServer`:
- Перед видаленням з `localStorage` надсилає `DELETE`-запит на сервер
- URL зображення зберігається в `data-url` атрибуті кнопки видалення

```js
// Було (тільки localStorage):
button.addEventListener('click', (event) => {
    storedFiles.splice(indexToDelete, 1);
    localStorage.setItem('uploadedImages', JSON.stringify(storedFiles));
});

// Стало (сервер + localStorage):
button.addEventListener('click', async (event) => {
    await deleteFromServer(imageUrl);  // видаляє файл з сервера
    storedFiles.splice(indexToDelete, 1);
    localStorage.setItem('uploadedImages', JSON.stringify(storedFiles));
});
```

---

## Рефакторинг

### 3. Виділення спільного коду в `common.js`

**Проблема:** Функції `updateTabStyles()` та обробники клавіатури (Escape/F5) були повністю дубльовані в `upload.js` та `images.js`.

**Файл:** `static/image-uploader/js/common.js` (новий)

**Рішення:** Створено окремий модуль `common.js` з трьома спільними функціями:

| Функція | Призначення |
|---------|-------------|
| `updateTabStyles()` | Підсвічує активну вкладку (Upload/Images) залежно від поточної сторінки |
| `registerKeyboardShortcuts(url)` | Реєструє перенаправлення по Escape/F5 на вказаний URL |
| `copyToClipboard(text)` | Копіювання в буфер обміну з fallback для HTTP |

Скрипт підключено в `upload.html` та `images.html` перед основними JS-файлами:
```html
<script src="/image-uploader/js/common.js"></script>
<script src="/image-uploader/js/upload.js"></script>
```

---

### 4. Виправлення `index.js` — доступ до DOM до завантаження сторінки

**Проблема:** Перші рядки `index.js` зверталися до DOM-елементів (`querySelectorAll('.hero__img')`) **до** події `DOMContentLoaded`. Це могло призвести до помилок, якщо скрипт завантажується раніше за HTML.

**Файл:** `static/image-uploader/js/index.js`

**Рішення:** Весь код переміщено всередину обробника `DOMContentLoaded`. Також виправлено друкарську помилку у назві змінної: `allImgBloks` → `allImgBlocks`.

```js
// Було (виконується до готовності DOM):
const allImgBloks = document.querySelectorAll('.hero__img');
allImgBloks[randomIndex].classList.add('is-visible');
document.addEventListener('DOMContentLoaded', function () { ... });

// Стало (все всередині DOMContentLoaded):
document.addEventListener('DOMContentLoaded', function () {
    const allImgBlocks = document.querySelectorAll('.hero__img');
    allImgBlocks[randomIndex].classList.add('is-visible');
    ...
});
```

---

### 5. Спрощення створення заголовка таблиці в `images.js`

**Проблема:** Три колонки заголовка (Name, Url, Delete) створювались окремими блоками коду з повторюваною структурою.

**Рішення:** Замінено на цикл:
```js
['Name', 'Url', 'Delete'].forEach(label => {
    const col = document.createElement('div');
    col.className = `file-col file-col-${label.toLowerCase()}`;
    col.textContent = label;
    header.appendChild(col);
});
```

---

## Перелік змінених файлів

| Файл | Тип змін |
|------|----------|
| `app.py` | Додано `do_DELETE`, `_handle_delete` |
| `static/image-uploader/js/common.js` | Новий файл — спільні утиліти |
| `static/image-uploader/js/upload.js` | Виправлено копіювання, прибрано дублювання |
| `static/image-uploader/js/images.js` | Додано серверне видалення, прибрано дублювання |
| `static/image-uploader/js/index.js` | Виправлено порядок доступу до DOM |
| `static/form/upload.html` | Підключено `common.js` |
| `static/form/images.html` | Підключено `common.js` |
