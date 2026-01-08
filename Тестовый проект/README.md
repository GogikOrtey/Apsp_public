Readme проекта и самописные инструкции по сборке и запуску контейнера

## Flask + Jinja: 3 страницы - тестовый проект

Минимальный пример Flask-приложения с тремя страницами на Jinja и общей шапкой-навигацией.

### Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Playwright (для 3-й страницы)

Локально (один раз после установки зависимостей) нужно поставить браузер Chromium:

```bash
python -m playwright install chromium
```

### Запуск

```bash
python app.py
```

Откройте в браузере:
- `http://127.0.0.1:5000/`
- `http://127.0.0.1:5000/page2`
- `http://127.0.0.1:5000/page3`

### Запуск в Docker (Linux/Windows/macOS)

В проект добавлены файлы: `Dockerfile`, `.dockerignore`, `docker-compose.yml`.

#### Предварительно: установка Docker

Если команда `docker` пишет что-то вроде `"docker" не является внутренней или внешней командой...` — значит Docker не установлен/не добавлен в PATH или не запущен.

**Windows 10/11 (самый простой путь)**
- Установи Docker Desktop (с официального сайта Docker) и запусти его.
- Убедись, что включена виртуализация в BIOS/UEFI.
- Если Docker Desktop попросит — включи/установи WSL2.
- Проверка в новом терминале:

```bash
docker --version
docker compose version
```

**Linux**
- Установи Docker Engine и Compose plugin (пакеты зависят от дистрибутива).
- Проверь:

```bash
docker --version
docker compose version
```

#### Вариант A: через docker compose (рекомендую)

1) Установите Docker Engine + Docker Compose plugin на Linux.
2) Скопируйте проект на Linux (через `git clone ...` или просто zip/флешку).
3) В папке проекта выполните:

```bash
docker compose up --build -d
```

Если при открытии 3-й страницы вы видите ошибку вида:
`BrowserType.launch: Executable doesn't exist ... /ms-playwright/...`
— это значит, что **в образе нет скачанных браузеров Playwright**. Решение: **пересобрать образ** (`docker compose up --build -d` или `docker build ...`) и, если переносите образ на другую машину через `docker save/load`, сделать `docker save` заново.

Открывайте в браузере:
- `http://<IP_вашего_Linux>:8000/`
- `http://<IP_вашего_Linux>:8000/page2`
- `http://<IP_вашего_Linux>:8000/page3`

Остановить:

```bash
docker compose down
```

#### Вариант B: без compose (ручные команды)

Сборка образа:

```bash
docker build -t apsp-test-simple:latest .
```

Запуск контейнера:

```bash
docker run --rm -p 8000:8000 --name apsp-web apsp-test-simple:latest
```

---

### Можно собрать контейнер на основной машине с проектом, и далее переместить и запустить его на Linux:

На Windows (в папке проекта):
```
docker build -t apsp-test-simple:0.1 .
docker save -o apsp-test-simple_v0.1.tar apsp-test-simple:0.1
```


Билд = 10-12 минут (если с браузерами Playwright внутри)


> apsp-test-simple:latest - это будет image  
>
> apsp-test-simple.tar - это будет упакованный image, который мы отправляем на сервер

Перенеси apsp-test-simple.tar на Linux, затем на Linux:

```
docker load -i apsp-test-simple.tar
docker run --rm -p 8000:8000 --name apsp-web apsp-test-simple:latest
```












---

## Запуск контейнера из снимка на Linux:

1. Установи Docker на Linux

Если это Ubuntu / Debian:

```
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable --now docker
```

Выполни:

```
sudo usermod -aG docker $USER
newgrp docker
```


Проверь:

```
docker --version
docker ps
```

И проверь `docker ps` ещё раз, если он выдавал ошибку 




---

### Запуск контейнера:

2. Скопируй файл образа на Linux

Например через scp:

```
scp apsp-test-simple_v0.01.tar user@linux-server:/home/user/
```

Или любым способом (SFTP, флешка, etc).

3. Загрузить образ в Docker

Перейди в каталог с .tar:

```
cd /home/user
```

Загрузи образ:

```
docker load -i apsp-test-simple_v0.01.tar
```

Ожидаемый вывод:

```
Loaded image: apsp-test-simple:0.01
```

(имя может отличаться)

Проверь:

```
docker images
```

Ты должен увидеть свой образ.

4. Запустить контейнер

Запуск стандартный:

```
docker run apsp-test-simple:0.01
docker run -d -p 8000:8000 --name apsp-test-container apsp-test-simple:latest
```

---

### А переживёт ли он перезагрузку сервера?

По умолчанию — нет.

После reboot контейнер не стартует.

Чтобы он автоматически поднимался:

```
docker run -d --restart unless-stopped apsp-test-simple:0.01
```

или если контейнер уже создан:

```
docker update --restart unless-stopped apsp-test
```






---

docker run -d -p 8000:8000 --name apsp-test-container apsp-test-simple:latest

apsp-test-simple_v0.01.tar - первая рабочая версия
apsp-test-simple_v0.3.tar - поменял циферку на 2 на главной странице
apsp-test-simple_v0.4.tar - добавил ChatGPT в проект
apsp-test-simple_v0.8.tar - последняя версия теста, с возможностью открыть несколько вкладок

————————————————————————

Загрузить снимок:
docker load -i НАЗВАНИЕ_СНИМКА.tar
docker load -i apsp-test-simple_v0.3.tar

Просмотреть все загруженные снимки в докере:
docker images

Запустить снимок в контейнер:
docker run -d -p 8000:8000 --name КОРОТКОЕ_НАЗВАНИЕ_ДЛЯ_УДОБСТВА НАЗВАНИЕ_СНИМКА:ВЕРСИЯ_СНИМКА
docker run -d -p 8000:8000 --name apsp-test-simple_v0.3 apsp-test-simple:0.3

Просмотреть запущенные контейнеры:
docker ps

Остановить контейнер по имени:
docker stop КОРОТКОЕ_НАЗВАНИЕ_ДЛЯ_УДОБСТВА
docker stop apsp-test-simple_v0.3

Запустить контейнер после остановки по имени:
docker start КОРОТКОЕ_НАЗВАНИЕ_ДЛЯ_УДОБСТВА
