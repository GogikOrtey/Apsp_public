Отлично! Теперь пройдём пошагово, что нужно сделать дальше.

## Шаг 1: Задать переменные окружения

Вам нужно задать 4 переменные окружения перед запуском MAIN_APP.py.

На Windows (в командной строке перед запуском):

set APSP_TELEGRAM_BOT_TOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER

set APSP_TELEGRAM_BOT_USERNAME=auto_gen_parsers_info_bot

set APSP_TELEGRAM_WEBHOOK_SECRET=любая_секретная_строка_123

set APSP_BASE_URL=http://127.0.0.1:5000

Что означают переменные:

- APSP_TELEGRAM_BOT_TOKEN — токен от BotFather (который вы добавили в файл на строках 13-16)

- APSP_TELEGRAM_BOT_USERNAME — username бота без @ (у вас auto_gen_parsers_info_bot)

- APSP_TELEGRAM_WEBHOOK_SECRET — любая секретная строка (придумайте свою, например my_secret_webhook_key_2026)

- APSP_BASE_URL — пока оставьте http://127.0.0.1:5000, позже обновим на публичный URL

## Шаг 2: Запустить Flask-сервер локально

Запустите MAIN_APP.py как обычно:

python MAIN_APP.py

Сервер должен запуститься на http://127.0.0.1:5000

## Шаг 3: Сделать локальный сервер доступным через HTTPS (ngrok)

Проблема: Telegram требует HTTPS для webhook, а у вас локальный HTTP.

Решение: Используем ngrok (бесплатный туннель).

### 3.1. Установить ngrok

1. Скачайте ngrok: https://ngrok.com/download

1. Распакуйте в любую папку

1. Зарегистрируйтесь на ngrok.com и получите authtoken

1. Выполните один раз (в папке с ngrok):

     ngrok config add-authtoken ВАШ_AUTHTOKEN

### 3.2. Запустить ngrok-туннель

В новом окне командной строки (Flask должен продолжать работать в первом окне):

ngrok http 5000

Вы увидите что-то вроде:

Forwarding  https://1234-abc-def.ngrok-free.app -> http://localhost:5000

Скопируйте этот HTTPS URL (например https://1234-abc-def.ngrok-free.app)

### 3.3. Обновить переменную окружения

Теперь нужно перезапустить Flask с новым BASE_URL.

Остановите Flask (Ctrl+C в первом окне), затем:

set APSP_TELEGRAM_BOT_TOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER

set APSP_TELEGRAM_BOT_USERNAME=auto_gen_parsers_info_bot

set APSP_TELEGRAM_WEBHOOK_SECRET=любая_секретная_строка_123

set APSP_BASE_URL=https://1234-abc-def.ngrok-free.app

python MAIN_APP.py

(Замените https://1234-abc-def.ngrok-free.app на ваш реальный URL от ngrok)

## Шаг 4: Зарегистрировать webhook в Telegram

Откройте в браузере следующий URL (подставьте свои значения):

https://api.telegram.org/bot<ТОКЕН>/setWebhook?url=<BASE_URL>/api/telegram/webhook/<SECRET>

Пример:

https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11/setWebhook?url=https://1234-abc-def.ngrok-free.app/api/telegram/webhook/my_secret_webhook_key_2026

Что подставить:

- <ТОКЕН> — ваш токен от BotFather

- <BASE_URL> — URL от ngrok (HTTPS!)

- <SECRET> — ваш секрет из APSP_TELEGRAM_WEBHOOK_SECRET

Ответ должен быть:

{"ok":true,"result":true,"description":"Webhook was set"}

### Проверка webhook

Откройте в браузере:

https://api.telegram.org/bot<ТОКЕН>/getWebhookInfo

Вы должны увидеть, что url установлен на ваш ngrok-адрес, и pending_update_count равен 0.

## Шаг 5: Проверить авторизацию

1. Откройте в браузере: http://127.0.0.1:5000/login_page

1. Нажмите "Привязать аккаунт Телеграм"

1. Должен открыться Telegram с чатом бота

1. Нажмите Start в чате

1. Бот должен написать: "Авторизация успешна"

1. Вернитесь в браузер — страница сама обновится и перекинет на главную

1. В правом верхнем углу должен появиться ваш Telegram username вместо no_account

## Важные моменты

Каждый раз при перезапуске ngrok:

- ngrok выдаёт новый URL

- Нужно обновить APSP_BASE_URL и заново зарегистрировать webhook (шаг 4)

Для продакшена (когда разместите на реальном сервере):

- Вместо ngrok используйте домен с SSL-сертификатом

- APSP_BASE_URL будет вашим постоянным доменом (например https://yourapp.com)

- Webhook нужно зарегистрировать только один раз

## Если что-то не работает

Бот не пишет "Авторизация успешна":

- Проверьте логи Flask (в консоли где запущен MAIN_APP.py)

- Проверьте getWebhookInfo — там должно быть 0 ошибок

- Убедитесь что ngrok работает (в его окне видны входящие запросы)

Страница не обновляется после нажатия Start:

- Проверьте консоль браузера (F12) на ошибки

- Попробуйте обновить страницу вручную — если всё прошло, увидите логин

Попробуйте выполнить эти шаги и напишите на каком застряли, если возникнут вопросы!