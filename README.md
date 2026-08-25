# VERUM Competitions Mini App

Telegram Mini App для регистрации участников на мероприятия VERUM.

## Что уже заложено

- список открытых мероприятий первым экраном;
- три типа регистрации: полная, короткая, регистрация учеников тренером;
- сохранение полного профиля участника за `telegram_id`;
- сохранение учеников за профилем тренера;
- массовая регистрация учеников;
- обязательный никнейм участника;
- расчет возраста на дату мероприятия;
- фильтрация номинаций по возрасту и полу;
- опыт в номинации хранится текстом;
- несколько номинаций на одного участника;
- админка по `ADMIN_IDS`;
- создание и архивирование мероприятий;
- добавление номинаций;
- список регистраций;
- Excel-экспорт с отдельным листом на каждую номинацию;
- Excel-шаблон для создания мероприятия и импорт заполненного шаблона в админке;
- Railway/Docker конфигурация.

## Локальный запуск

Рекомендуемый Python: `3.12`. В текущем Windows-окружении Python `3.14` может пытаться собирать часть зависимостей из исходников.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
npm --prefix frontend install
npm --prefix frontend run build
$env:PYTHONPATH="backend"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Для локальной авторизации без Telegram запусти backend и Vite отдельно:

```powershell
$env:PYTHONPATH="backend"
$env:ALLOW_DEV_AUTH="true"
$env:ADMIN_IDS="1001"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

$env:VITE_API_BASE="http://127.0.0.1:8000"
$env:VITE_DEV_TELEGRAM_ID="1001"
npm --prefix frontend run dev
```

Открыть приложение: `http://127.0.0.1:5173`. Dev-авторизация доступна только
в Vite development mode и должна быть выключена в production.

## Railway

Переменные окружения:

- `BOT_TOKEN` - новый токен из BotFather;
- `DATABASE_URL` - PostgreSQL URL от Railway;
- `WEBAPP_URL` - публичный URL Railway-сервиса;
- `APP_ENV=production`;
- `ADMIN_IDS` - Telegram ID админов через запятую;
- `SESSION_SECRET` - случайный секрет длиной не менее 32 символов;
- `ALLOW_DEV_AUTH=false`;
- `ALLOWED_ORIGINS` - публичный URL приложения.

Токен, который был отправлен в чат, нужно перевыпустить в BotFather перед деплоем.

Логотипы мероприятий сохраняются в PostgreSQL, а не в файловой системе контейнера Railway. Поэтому новые загруженные картинки не пропадают после redeploy.

Миграции запускаются Railway до старта приложения:

```bash
alembic upgrade head
```

В production приложение не изменяет схему базы на старте. Для локальной SQLite-базы
таблицы создаются автоматически. Перед production-миграцией обязателен backup и
проверка восстановления.

## GitHub

Репозиторий:

```bash
git remote add origin https://github.com/koych77/VERUM-Competitions-.git
```
