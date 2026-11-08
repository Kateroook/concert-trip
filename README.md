# ConcerTrip

Відстеження концертів улюблених артистів у Європі та Великій Британії: коли відкриються продажі, коли повернуться квитки на розпродані події та скільки приблизно коштуватиме поїздка.

Навчальний проєкт. Команда з двох людей, два спринти, 12.10 – 07.11.2026.

## Що робить

- збирає події з Ticketmaster, одного локального продавця й резервного набору;
- зводить назви секторів різних продавців до спільної класифікації: танцпол, сидячі місця, VIP;
- стежить за списком відстежуваних артистів і надсилає сповіщення в Telegram про старт продажів і повернення квитків;
- показує орієнтовний діапазон вартості поїздки до події.

Сповіщення надсилаються **лише за явно доданими артистами**. Оцінка відповідності смакам впливає тільки на порядок подій у стрічці.

## Розгортання

Потрібен Python 3.11 або новіший.

```bash
git clone <адреса-репозиторію>
cd concertrip

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

Застосунок запускається й без жодного ключа — працює на резервному наборі подій. Щоб підключити зовнішні джерела, заповніть у `.env` те, що потрібно: ключ Ticketmaster для збору подій, токен Telegram для сповіщень, ключ Anthropic для витягу дат із тексту анонсу.

Запуск інтерфейсу:

```bash
streamlit run concertrip/ui/app.py
```

Тести:

```bash
pytest
```

## Backend API

Після створення або оновлення бази імпортуйте демонстраційні події та запустіть API:

```bash
alembic upgrade head
python -m concertrip.sources.seed
uvicorn concertrip.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Перевірка:

```bash
curl http://127.0.0.1:8000/health
```

Події захищені авторизацією. Для локального режиму `AUTH_DEV_MODE=true` endpoint реєстрації повертає verification token у відповіді та записує його в log. Послідовність перевірки:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"correct horse battery staple"}'

curl -X POST http://127.0.0.1:8000/api/v1/auth/verify-email \
  -H 'Content-Type: application/json' \
  -d '{"token":"<verificationToken>"}'

curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"correct horse battery staple"}'
```

Після login передайте `accessToken` як `Authorization: Bearer <token>` для запиту до `/api/v1/events`.

## AI recommendations

Для запуску neural embeddings окремо встановіть optional dependency:

```bash
pip install -r requirements-ai.txt
```

Без неї backend і тести працюють, але `/api/v1/recommendations` поверне помилку про відсутню AI dependency. Модель кешує embeddings подій і профілю користувача в БД, тому vectors не перераховуються на кожен запит.

## Spotify integration

Створіть Web API app у [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), додайте Redirect URI з `.env` і заповніть backend-only settings:

```env
SPOTIFY_CLIENT_ID=<client-id>
SPOTIFY_CLIENT_SECRET=<client-secret>
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/api/v1/integrations/spotify/callback
SPOTIFY_TOKEN_ENCRYPTION_KEY=<random-secret>
```

Для Development Mode власник Spotify app повинен мати Premium, а тестові користувачі мають бути в allowlist. Mobile не отримує Spotify tokens.

Після login:

```bash
curl -H "Authorization: Bearer <access-token>" \
  http://127.0.0.1:8000/api/v1/integrations/spotify/authorize

curl -X POST -H "Authorization: Bearer <access-token>" \
  http://127.0.0.1:8000/api/v1/integrations/spotify/sync
```

Поточний sync імпортує top artists за трьома періодами та recently played. Preferences є підготовленими даними для наступного recommendation score/AI layer.

## Ticketmaster sync

Ticketmaster Discovery API використовує ключ лише на backend. Додайте його в `.env`:

```env
TICKETMASTER_API_KEY=<your-key>
```

Застосуйте міграції та перевірте ключ без запису у БД:

```bash
alembic upgrade head
python -m concertrip.sources.ticketmaster --dry-run --country GB --minimum-events 1
```

Повний sync працює по країнах із `COUNTRIES` і зупиняється після 200 унікальних подій:

```bash
python -m concertrip.sources.ticketmaster --minimum-events 200
```

Client дотримується ліміту Ticketmaster у 5 запитів на секунду, повторює тимчасові `429/5xx` помилки та не виводить API key у log. TBA/TBD події зберігаються з `dateStatus`, але без вигаданої дати.

## Mobile API connection

React Native використовує `API_BASE_URL` у `mobile/src/config.ts`:

- Android emulator: `http://10.0.2.2:8000`;
- iOS simulator: `http://127.0.0.1:8000`;
- фізичний Android-пристрій: LAN IP комп'ютера, наприклад `http://192.168.1.10:8000`.

Запуск мобільної частини:

```bash
cd mobile
npm start
# в іншому терміналі
npm run android
```

Міграції бази даних:

```bash
alembic upgrade head
alembic downgrade base
```

## Структура

```
concertrip/
  config.py              налаштування з .env
  db.py                  підключення до бази й базовий клас моделей
  models.py              моделі подій, користувачів і auth-токенів
  api/                    FastAPI endpoints для мобільного клієнта
  sources/
    ticketmaster.py      CT-21  клієнт до API Ticketmaster
    local_parser.py      CT-22  парсер локального продавця
    seed.py              CT-23  імпорт резервного набору
  normalize/
    ticket_type.py       CT-31  класифікація типів квитків   [готово]
    artists.py           CT-32  зведення дублікатів артистів
  ranking/
    score.py             CT-41  оцінка відповідності події
  notify/
    telegram_bot.py      CT-54  підписки й розсилка сповіщень
  ui/
    app.py               CT-71  веб-інтерфейс
data/
  seed_events.csv        резервний набір подій для демонстрації
alembic/                  міграції схеми бази даних
tests/                   тести
docs/                    нотатки з досліджень і рішення щодо архітектури
```

Кожен модуль підписаний ключем задачі в Jira, щоб було видно, звідки він узявся й хто за нього відповідає.

## Домовленості в команді

- Гілка на задачу: `ct-21-ticketmaster-client`, `ct-31-ticket-type`.
- Задача не йде в Done без перегляду другим учасником: колонка In Review обов'язкова.
- Файл `.env` у репозиторій не потрапляє. Якщо з'являється новий ключ, додайте його в `.env.example` порожнім і напишіть у чат.
- Нова залежність — рядок у `requirements.txt` із точною версією.

## Стан робіт

| Задача                           | Що зроблено                                                 |
| -------------------------------- | ----------------------------------------------------------- |
| CT-11 Каркас репозиторію         | готово                                                      |
| CT-31 Класифікація типів квитків | готово, точність 20 із 20 на тестовому наборі з п'яти країн |
| решта                            | за планом спринтів                                          |
