"""
Это новый главный скрипт, который будет работать с playwright, агентами, и остальными функциями

На вход к нему будет подаваться ссылка на товар на любой сайт

И в результате он должен будет сгенерировать код парсера этого сайта, и сохранить в result_code.ts
"""

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

from HGF_main_page_selector_and_semantic_handler import *

from new_program.html_toolkit import *
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT

"""

Текущие задачи:

- Доработать код в get_html_frame, и вынести его в html_toolkit
- Реализовать все инструменты, которые описал gemini
    - Реализовать инструмент, который возвращает html между двумя найденными вхождениями одинаковых селекторов
    и возможно как-то собирает полный элемент между ними. Возвращает с доп. информацией
    - Может быть необходимо добавить чистку от ``` в ответах от HGF и TNF
- Добавить функционал local_storage в агента
- Выписать, что бы он смог сделать всё что нужно на 2й фазе




Сайты, на которых тестирую:

https://makitaclub.ru
https://makita-land.ru
https://kotel-nasos.ru

som1.ru
krason.ru

https://makitatrading.ru
https://systemarf.ru
https://makita-snab.ru
https://line-tools.ru
https://makita-online.ru

Доп. ссылки прописаны внизу этого файла

"""









def main_processer(input_url):
    print("Запускаем основной процесс")

    # 1. Чистим входящий url - до host, что бы получить ссылку на главную страницы
    url = normalize_url(input_url)

    # 2. Запускаем браузер и переходми на эту страницу
        # Дожидаемя полной загрузки страницы, но с таймаутом в 20 секунд
    
    # 3. HGF_main_page_selector_and_semantic_handler

    ### Тут возможно стоит брать html контент из playwright
    ######## И не понятно, надо ли проверять, отличается ли контент в браузере от контента по прямому запросу, без него
    html_content = get_html_from_cache(url)
    html_content_zip = clean_html_universal(html_content)

    # save_page_html(html_content, filename = "page_html.html")
    # save_page_html(html_content_zip, filename = "page_html_zip.html")

    HGF_result = HGF_main_page_selector_and_semantic_handler(html_content_zip)
    print(f"\nHGF_result:\n")
    print(HGF_result)

    """
    Пример результата в HGF_result:
    {
        "status": "ok",
        "error_type": null,
        "analysis_message": "Страница успешно обработана",
        "semantics": ["инструмент", "дрель", "шуруповерт", "перфоратор", "болгарка", "пила", "лобзик", "шлифмашина", "пылесос", "аккумулятор"],
        "search_input_selectors": [
            "#woocommerce-product-search-field-0",
            ...
        ],
        "search_button_selectors": [
            "form.woocommerce-product-search button[type=\"submit\"]",
            ...
        ]
    }
    """


























# link = "https://makitaclub.ru"
# link = "https://kotel-nasos.ru/nastennyy-gazovyy-kotel-28-kvt-eca-gerda-28-hm-ng_1/"
link = "https://makitatrading.ru"
main_processer(link)

















# region Доп. функции

def save_page_html(html: str, filename: str = "page_html.html") -> str:
    """
    Сохраняет HTML в файл рядом со скриптом и возвращает путь к файлу.
    
    Args:
        html: html-содержимое страницы
    """
    print("Сохраняем html страницы в файл", filename)
    output_path = Path(__file__).resolve().parent / filename
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


































"""
Задачи на будущее:


- Вот на этом сайте данные поиска подгружаются POST запросом:
https://www.krason.ru/search

- В очень редких случаях пагинации на странице нет вообще - сайт выдаёт все результаты на одной странице. Но тогда на больших запросах будет много результатов (можно будет проверить, если количество результатов плавает на больших запросах, и везде > 100, то скорее всего пагинации нет) - пока что следует поставить заглушку на этот случай, в будущем доработать
  - Иногда вместо пагинации есть бесконечная автоподгрузка, через запросы - пока что следует поставить заглушку на этот случай, в будущем доработать
  - Иногда, очень редко, нет ни кнопки последней страницы, ни указания количества результатов. Тогда нужно будет реализовывать динамическую пагинацию - пока что следует поставить заглушку на этот случай, в будущем доработать
- Можно будет в будущем обработать ситуацию когда есть кнопка "Показать ещё"
    - Бесконечная прокрутка: Если пагинация реализована через кнопку «Показать еще» (Load More) без нумерации страниц, укажи селектор этой кнопки в поле `next_page_button` и пометь тип пагинации как `load_more`.

Пагинация: Кнопка "Вперед" (Next)
Замечание: Ты ищешь "Контейнер", "Страницу 2" и "Последнюю страницу". Но часто в скрейпинге самым надежным способом прохода по страницам является кнопка "Next" (Следующая ->). Почему:
    - "Страницы 2" может не быть (если всего 1 страница).
    - "Последней страницы" может не быть (бесконечный скролл или "load more").
    - Кнопка "Next" — самый универсальный паттерн. Совет: Рекомендую добавить поле pagination_next_button_selectors. Это сильно повысит надежность краулера.
"""


"""
Старые простые:
(смотрел по простоте реализации)

https://domo-terra.ru
https://domplitok.ru
https://dvkeramik.ru
https://e-dz.ru
https://electron.bg
https://www.electrovek.ru
https://www.elemor.ru
https://ceraboom.ru
https://ceramama.ru
https://ceramicmall.ru
https://ceramictilecenter.ru
https://ceram-stroy.ru
https://www.ceramtrade.ru
https://championtool.ru
https://www.chipdip.ru        
https://comfort-klimat.ru    
https://cosmofun.ru          
https://c-s-k.ru             
https://galen.bg           
https://galleryceramics.ru 
https://gazovik-omsk.ru    
https://gaz-shop78.ru      
https://gidro-top.ru       
https://glavsantex.ru      
https://goodzone23.ru      
https://gra-nit.ru         
https://gresstore.ru       
https://gastehmarket.ru
https://daewoo-power.ru
https://chiedocover.ru
https://edrinks.bg
https://dom-septik24.ru 
https://makita-line.ru

Обработать другие расписанные ситуации

"""


