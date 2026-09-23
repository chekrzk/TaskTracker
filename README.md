# Жир

Учебное приложение для управления компаниями, продуктами, командами и задачами.
Техническое задание находится в `AGENT.md`.

## Локальный запуск в Windows PowerShell

Используемое окружение: Python 3.14, Django 5.2, SQLite.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Открыть http://127.0.0.1:8000/. Активировать виртуальное окружение не требуется:
команды используют его интерпретатор напрямую.

Настройки рассчитаны на локальную разработку: `DEBUG=True`, разрешены хосты
`localhost` и `127.0.0.1`, используется ключ только для разработки.
База `db.sqlite3` создаётся командой `migrate` и не включается в Git.

## Этап 1: каркас проекта

- `manage.py` — команды управления Django.
- `config/settings.py` — стандартные приложения Django и `tracker`, SQLite,
  русский язык интерфейса, часовой пояс `Asia/Yekaterinburg`, поиск шаблонов
  и статических файлов внутри приложений. `APP_DIRS=True` включает поиск
  шаблонов в `tracker/templates/`, `django.contrib.staticfiles` находит файлы
  в `tracker/static/`. `STATIC_URL=/static/`, каталог сборки `STATIC_ROOT`
  указывает на `staticfiles/` в корне проекта.
- `config/urls.py` — подключение маршрутов `tracker` и стандартного `/admin/`.
- `config/asgi.py` и `config/wsgi.py` — стандартные точки входа сервера.
- `tracker/apps.py` — конфигурация приложения.
- `tracker/urls.py` — маршрут `/` с именем `tracker:home`.
- `tracker/views.py` — представление стартовой страницы.
- `tracker/templates/tracker/home.html` — стартовая страница «Жир».
- `tracker/static/tracker/css/style.css` — минимальное оформление страницы
  и проверка подключения статики; полноценная вёрстка относится к этапу 5.
- `tracker/models.py`, `tracker/admin.py`, `tracker/tests.py` и
  `tracker/migrations/__init__.py` — заготовки, созданные `startapp`.
- `requirements.txt` — фиксированная версия Django.
- `.gitignore` — исключения для окружения, базы, кеша Python и локальных настроек.

Модели предметной области, регистрация, dashboard и остальные возможности
будут реализованы на следующих этапах. `/` пока является публичной стартовой
страницей. Стандартный маршрут `/admin/` подключён, суперпользователь ещё не создан.

## Проверка конфигурации

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py showmigrations
.\.venv\Scripts\python.exe manage.py findstatic tracker/css/style.css
```

При завершении этапа 1 проверено:

- `manage.py check` — ошибок нет.
- `pip check` — конфликтов зависимостей нет.
- Все 18 стандартных миграций Django применены к SQLite.
- `findstatic` находит `tracker/css/style.css`.
- Сервер запущен командой `runserver 127.0.0.1:8000 --noreload`;
  HTTP-запросы к `/` и `/static/tracker/css/style.css` вернули `200`.
  Проверены русский язык HTML, ссылка на CSS и содержимое CSS.
- После проверки сервер остановлен. Для запуска используйте команду выше.
