# Настройка Telegram-бота для APSP

## Зачем нужен Telegram-бот

Бот используется для:
- **Авторизации пользователей** (вместо паролей — привязка к Telegram-аккаунту)
- **Уведомлений** о старте и завершении генерации парсеров

## Быстрый старт (локальная разработка)

### 1. Создать бота в BotFather

1. Откройте Telegram и найдите `@BotFather`
2. Отправьте команду `/newbot`
3. Задайте имя и username бота (должен заканчиваться на `bot`)
4. BotFather выдаст **токен** вида `123456:ABC-DEF...`

### 2. Настроить `MAIN_APP.py`

Откройте `MAIN_APP.py` и замените значения на свои:

```python
# Вставьте токен от BotFather
os.environ.setdefault("APSP_TELEGRAM_BOT_TOKEN", "123456:ABC-DEF...")

# Укажите username бота без @
os.environ.setdefault("APSP_TELEGRAM_BOT_USERNAME", "ваш_бот_username")

# Придумайте секрет (любая строка)
os.environ.setdefault("APSP_TELEGRAM_WEBHOOK_SECRET", "ваш_секретный_ключ")

# Пока оставьте локальный адрес
os.environ.setdefault("APSP_BASE_URL", "http://127.0.0.1:5000")
```

### 3. Запустить Flask

```bash
python MAIN_APP.py
```

### 4. Настроить ngrok (для webhook)

**Почему:** Telegram требует HTTPS для webhook, а локальный сервер работает на HTTP.

#### Установка ngrok

1. Скачайте: https://ngrok.com/download
2. Зарегистрируйтесь и получите authtoken
3. Выполните один раз:
   ```bash
   ngrok config add-authtoken ВАШ_AUTHTOKEN
   ```

#### Запуск туннеля

В **новом окне** командной строки:

```bash
ngrok http 5000
```

Вы увидите HTTPS URL вида: `https://1234-abc-def.ngrok-free.app`

#### Обновить BASE_URL

**Остановите Flask** (Ctrl+C) и в `MAIN_APP.py` замените:

```python
os.environ.setdefault("APSP_BASE_URL", "https://1234-abc-def.ngrok-free.app")
```

Запустите Flask снова: `python MAIN_APP.py`

### 5. Зарегистрировать webhook

Откройте в браузере (подставьте свои значения):

```
https://api.telegram.org/bot<ТОКЕН>/setWebhook?url=<BASE_URL>/api/telegram/webhook/<SECRET>
```

**Пример:**
```
https://api.telegram.org/bot123456:ABC-DEF.../setWebhook?url=https://1234-abc-def.ngrok-free.app/api/telegram/webhook/my_secret_webhook_key_2026
```

**Ожидаемый ответ:**
```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

### 6. Проверить работу

1. Откройте `http://127.0.0.1:5000/login_page`
2. Нажмите **"Привязать аккаунт Телеграм"**
3. В Telegram нажмите **Start**
4. Бот должен написать **"Авторизация успешна"**
5. Страница в браузере автоматически обновится

## Продакшен (Docker + реальный домен)

### Для Docker

Создайте файл `.env` в корне проекта:

```env
APSP_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
APSP_TELEGRAM_BOT_USERNAME=ваш_бот_username
APSP_TELEGRAM_WEBHOOK_SECRET=ваш_секретный_ключ
APSP_BASE_URL=https://ваш-домен.com
```

В `docker-compose.yml` или при запуске контейнера пробросьте эти переменные:

```yaml
environment:
  - APSP_TELEGRAM_BOT_TOKEN=${APSP_TELEGRAM_BOT_TOKEN}
  - APSP_TELEGRAM_BOT_USERNAME=${APSP_TELEGRAM_BOT_USERNAME}
  - APSP_TELEGRAM_WEBHOOK_SECRET=${APSP_TELEGRAM_WEBHOOK_SECRET}
  - APSP_BASE_URL=${APSP_BASE_URL}
```

### Webhook на продакшене

После деплоя на сервер с SSL-сертификатом:

1. Зарегистрируйте webhook **один раз** (замените на свои значения):
   ```
   https://api.telegram.org/bot<ТОКЕН>/setWebhook?url=https://ваш-домен.com/api/telegram/webhook/<SECRET>
   ```

2. URL webhook будет постоянным (не меняется как у ngrok)

## Проверка webhook

Проверить статус webhook можно в браузере:

```
https://api.telegram.org/bot<ТОКЕН>/getWebhookInfo
```

Должно быть:
- `url` установлен на ваш домен
- `pending_update_count` равен 0
- `last_error_date` отсутствует или старый

## Отладка

### Бот не отвечает

1. Проверьте логи Flask (в консоли где запущен `MAIN_APP.py`)
2. Проверьте `getWebhookInfo` — там не должно быть ошибок
3. Убедитесь что ngrok работает (в его окне видны входящие запросы)

### Страница не обновляется

1. Откройте консоль браузера (F12) — там будут ошибки
2. Проверьте что Flask доступен по `http://127.0.0.1:5000`
3. Попробуйте обновить страницу вручную

### Webhook не работает после перезапуска ngrok

ngrok при каждом запуске **выдаёт новый URL**. Нужно:
1. Скопировать новый URL из окна ngrok
2. Обновить `APSP_BASE_URL` в `MAIN_APP.py`
3. Перезапустить Flask
4. Заново зарегистрировать webhook (шаг 5)

## Дополнительно

### Удалить webhook

Если нужно отключить уведомления:

```
https://api.telegram.org/bot<ТОКЕН>/deleteWebhook
```

### Тестирование без webhook

Можно временно закомментировать строки с `send_bot_message()` в коде — авторизация будет работать, но уведомления не будут приходить.

### Безопасность

- Не коммитьте токен бота в Git (он уже в `.gitignore`)
- В продакшене используйте сильный `WEBHOOK_SECRET`
- Папки `_telegram_auth/` и `_telegram_users/` не попадают в Git

