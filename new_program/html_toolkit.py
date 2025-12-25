"""

"""

from bs4 import BeautifulSoup, Comment, NavigableString

# region Импорты
# Чтобы при запуске файла из этой папки были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import os
import json
import copy
import traceback
import time
from typing import Any
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT







# Приводит любую ссылку на сайт к виду https://makitaclub.ru
def normalize_url(url: str) -> str:
    """
    Приводит любую ссылку на сайт к виду https://makitaclub.ru
    """
    url = url.strip()

    # Если схема не указана — добавляем https
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    domain = parsed.netloc.lower()

    # Убираем www.
    if domain.startswith("www."):
        domain = domain[4:]

    result =  f"https://{domain}"
    print("Нормализовали ссылку, получилось:", result)
    return result







# Очищает html перед отправкой в LLM
def clean_html_universal(html_content: str) -> str:
    """
    Универсальная очистка HTML для LLM (Black-list подход).
    Удаляет скрипты и стили, но сохраняет структуру, мета-теги и контент.
    Длинные тексты и Base64-изображения обрезаются.
    """
    print(f"\nСжимаем страницу\n")

    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Удаляем ТОЛЬКО явный технический мусор
    # script - исполняемый код
    # style - глобальные стили (забивают контекст)
    # noscript - дублирующий контент
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()

    # 2. Удаляем комментарии (часто содержат старый код)
    for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 3. Обработка SVG
    # Оставляем сам тег SVG (чтобы было видно, что тут иконка), но чистим внутренности
    for svg in soup.find_all('svg'):
        # Сохраняем атрибуты, но удаляем вложенные path, circle и т.д.
        svg.clear() 
        # Можно добавить пометку, что контент удален
        svg.append(NavigableString(""))

    # 4. Обработка атрибутов (Base64 и события)
    for tag in soup.find_all(True):
        attrs_to_modify = {}
        for attr, value in tag.attrs.items():
            # Проверка на Base64 (картинки, зашитые в код)
            # Если значение атрибута - строка и начинается с data:image
            if isinstance(value, str) and value.startswith('data:'):
                if len(value) > 50: # Если это не коротенький пиксель
                    attrs_to_modify[attr] = "<--BASE64_DATA_TRUNCATED-->"

        # Применяем изменения атрибутов
        for attr, val in attrs_to_modify.items():
            if val is None:
                del tag.attrs[attr]
            else:
                tag.attrs[attr] = val

        # Удаляем пустые атрибуты (только те, которые реально пустые: "", [], None)
        # Мы оставляем 0, False и другие значения, которые могут быть важны
        tag.attrs = {
            k: v for k, v in tag.attrs.items() 
            if v is not None and (not hasattr(v, '__len__') or len(v) > 0)
        }

    # 5. Умное обрезание длинного текста (Truncate)
    # Проходимся по всем текстовым узлам
    for text_node in soup.find_all(text=True):
        # Игнорируем пробельные узлы
        if not text_node.strip():
            continue
        
        # Если текст слишком длинный (например, статья или описание)
        if len(text_node) > 250:
            # Оставляем 200 символов сначала и 50 с конца
            head = text_node[:200]
            tail = text_node[-50:]
            # Заменяем содержимое узла
            new_text = f"{head} ... <--TRUNCATED_TEXT--> ... {tail}"
            text_node.replace_with(new_text)

    # 6. Финальная сборка
    # cleaned_html = soup.prettify() # Формирует красивый html код, но нам нужен именно сжатый

    # Сборка компактным методом
    content = str(soup)
    # Удаляем лишние пустые строки, которые могли остаться после decompose()
    cleaned_html = "\n".join([line.strip() for line in content.splitlines() if line.strip()])

    # Вычисление и вывод статистики
    original_len = len(html_content)
    cleaned_len = len(cleaned_html)
    compression_percent = round((1 - cleaned_len / original_len) * 100, 2) if original_len else 0

    print(f"Исходное количество символов: {original_len}")
    print(f"После сжатия: {cleaned_len}")
    print(f"Страница сжалась на {compression_percent}%\n")

    return cleaned_html




# region Max pagination
"""
Оригинал на JS:

    let totalPages = Math.max(...$(".module-pagination__wrapper > a").get().map(item => +$(item).text().trim()).filter(Boolean))

Полная версия на питоне:

    from bs4 import BeautifulSoup

    # Допустим, html_content — это содержимое вашей страницы
    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Находим все ссылки 'a' внутри контейнера
    links = soup.select(".module-pagination__wrapper > a")

    # 2. Извлекаем текст, очищаем его, переводим в числа и фильтруем (убираем ошибки и пустые значения)
    page_numbers = []
    for item in links:
        text = item.get_text(strip=True)
        if text.isdigit(): # Аналог .filter(Boolean) и проверки на число
            page_numbers.append(int(text))

    # 3. Находим максимум (с проверкой на пустой список, чтобы не было ошибки)
    total_pages = max(page_numbers) if page_numbers else 0

    print(total_pages)

Компактная версия на питоне:

    total_pages = max([int(a.text.strip()) for a in soup.select(".module-pagination__wrapper > a") if a.text.strip().isdigit()] or [0])


"""





"""

    Осталось реализовать:

    - get_html_frame (дописать) - Доработать код в get_html_frame, и вынести его в html_toolkit
    - Формирование curl запроса, с body, заголовками и прочим
    - Проверяет, валидный ли это селектор Cheerio
    - Получение всех запросов в браузере, с их параметрами и частью body (обрезанной в середине)
    - Получение результатов конкретного запроса, с указанием сколько контента из ответа нужно показать
    - Поиск запросов в которых есть вхождение подстроки (как в результатах так и в запросах, это можно будет например контролировать параметрами)    
    - Реализовать инструмент, который возвращает html между двумя найденными вхождениями одинаковых селекторов
    и возможно как-то собирает полный элемент между ними. Возвращает с доп. информацией
        - Да, это прям надо сделать автоматически, для валидации селектора товара

"""