""" 
Здесь будет реализация алгоритма работы агента для 4го шага
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
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *

from reasoning_agent.agent_main import *

from playwright_tool.playwright_toolkit import *  # регистрирует инструменты playwright
from new_program.html_toolkit import *  # регистрирует инструменты html_tool


""" 



"""






main_task_all = """

Задача: Во входных данных будут даны 3 ссылки на страницы. Нужно будет пройтись по ним, и собрать по 5 ссылок на товары, с каждой страницы. Если найдено меньше 5 ссылок, вернуть все найденные (либо []). 

————————————————————————

Инструкция:

1. Перейди на страницу указанную в поле first_url в input_data (инструмент goto_url)

2. Получи первые 5 элементов ссылок на товары, используя селектор из поля selector_product из input_data, при помощи инструмента find_elements.

selector_product — CSS-селектор, возвращающий элементы <a> или элементы, внутри которых есть <a> с ссылкой на товар. Из полученных объектов нужно будет извлечь ссылки.

    - Если в input_data в поле additional_processing_for_the_link_value указано true, то значит для ссылки нужна дополнительная обработка. Чаще всего, в начало ссылки нужно подставить HOST текущего сайта (протокол и домен), что бы она стала валидной (преврати относительную ссылку в абсолютную, используя текущий URL страницы).

    Например, если мы сейчас на сайте https://kotel-nasos.ru/...
    и ссылка выглядит так: href="/elektricheskiy-kotel-evan-epo-pro-60/"
    То скорее всего что бы сделать её валидной, нужно будет добавить HOST в начало. В этом примере получится вот так: https://kotel-nasos.ru/elektricheskiy-kotel-evan-epo-pro-60/

    Далее нужно будет проверить, что ссылка получилась валидная. Используя инструмент check_url_status (для первой ссылки).

    Когда валидная ссылка будет получена, зафиксируй в memory, какая обработка нужна для извлекаемых со страницы ссылок, что бы они стали валидными.

    - Если в input_data в поле additional_processing_for_the_link_value указано false, то значит скорее всего дополнительной обработки для ссылок не требуется. Также проверь одну ссылку через инструмент check_url_status, и зафиксируй в memory. Если обработка всё же нужна, то определи какая именно. 

Обработка, определённая на первой странице, применяется ко всем следующим страницам без повторной проверки.

3. Запиши ранее полученные первые 5 ссылок на товары из этой страницы в result в поле five_links_1. Нужно записать именно валидные ссылки (если нужна дополнительная их обработка)

4. Перейди на вторую страницу, указанную в input_data в поле second_url

5. Получи первые 5 элементов ссылок на товары, используя селектор из поля selector_product из input_data, при помощи инструмента find_elements.

6. Запиши их в result в поле five_links_2. Нужно записать именно валидные ссылки (если нужна дополнительная их обработка)

7. Перейди на третью страницу, указанную в input_data в поле third_url

8. Получи первые 5 элементов ссылок на товары, используя селектор из поля selector_product из input_data, при помощи инструмента find_elements.

9. Запиши их в result в поле five_links_3. Нужно записать именно валидные ссылки (если нужна дополнительная их обработка)

10. На этом задача будет завершена.

————————————————————————

Входные данные (input_data):

"""




""" 
Входные данные:
{
    "first_url"
    "second_url"
    "third_url"
    "selector_product"
    "additional_processing_for_the_link_value"
}

Результаты:
{
    "five_links_1",
    "five_links_2",
    "five_links_3",
}

"""










# Схема результата
main_result_schema = {
    "five_links_1": {
        "type": "list[str]",
        "required": True,
        "description": "Пять ссылок на товары с первой страницы"
    },
    "five_links_2": {
        "type": "list[str]",
        "required": True,
        "description": "Пять ссылок на товары со второй страницы"
    },
    "five_links_3": {
        "type": "list[str]",
        "required": True,
        "description": "Пять ссылок на товары с третьей страницы"
    }
}

# Шаблон результата, который агент заполняет в процессе работы
main_result_template = {
    "five_links_1": None,
    "five_links_2": None,
    "five_links_3": None
}

















# main_plan = {
#     "steps": [
#         {
#             "step_id": 1,
#             "goal": "Зафиксировать URL первой страницы выдачи (1 шаг алгоритма)",
#             "fills": [
#                 "start_page_url"
#             ]
#         },
#         {
#             "step_id": 2,
#             "goal": "Перейти на 2-ю страницу через пагинацию и зафиксировать новый URL (1 шаг алгоритма)",
#             "fills": [
#                 "url_for_2_page",
#                 "search_output_set_by_add_query"
#             ]
#         },
#         {
#             "step_id": 3,
#             "goal": "По разнице start_page_url и url_for_2_page определить параметр пагинации и описать его (2 шаг алгоритма)",
#             "fills": [
#                 "info_from_page_parameter"
#             ]
#         },
#         {
#             "step_id": 4,
#             "goal": "Выполнить поиск по другому запросу и зафиксировать URL новой страницы (3 шаг алгоритма)",
#             "fills": [
#                 "url_for_second_search_query"
#             ]
#         },
#         {
#             "step_id": 5,
#             "goal": "По разнице start_page_url и url_for_second_search_query определить параметр поискового запроса и описать его (3 шаг алгоритма)",
#             "fills": [
#                 "info_from_search_query_parameter"
#             ]
#         },
#         {
#             "step_id": 6,
#             "goal": "Сформировать JS-код генерации URL на основе info_from_page_parameter и info_from_search_query_parameter (4 шаг алгоритма)",
#             "fills": [
#                 "result_code_url_builder"
#             ]
#         }
#     ]
# }






def agent_step_6_1_get_links_for_product(input_data, search_request):
    # Приводим input_data к строке
    if isinstance(input_data, str):
        input_data_str = input_data
    else:
        try:
            input_data_str = json.dumps(input_data, ensure_ascii=False, indent=4, default=str)
        except Exception:
            input_data_str = str(input_data)

    task = (
        f"Сейчас в браузере Playwright открыта страница результатов товаров с поисковой выдачи по запросу '{search_request}'." +
        main_task_all + 
        input_data_str )

    resulr_answer = orchestrate(
        task = task,
        max_steps = 40,
        result_schema = main_result_schema,
        result_template = main_result_template,
        # plan = main_plan,
        # step_by_step_running = False, # Разрешаем агенту работать автоматически
    ) 

    result_task = get_result()
    return result_task




# Проверка 1:


input_data_test = {
    "first_url": "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
    "second_url": "https://makitaclub.ru/page/2/?s=инструмент&post_type=product",
    "third_url": "https://makitaclub.ru/?s=%D0%B4%D1%80%D0%B5%D0%BB%D1%8C&post_type=product",
    "selector_product": ".products .product-card a.stretched-link[href*='/products/']",
    "additional_processing_for_the_link_value": "false"
}



# Запускаю браузер с видимым окном
launch_browser(headless = False)

goto_url( 
    url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
    wait_until = "load",
    timeout = 30_000
)

search_request_test = "инструмент"

resilt = agent_step_6_1_get_links_for_product(input_data_test, search_request_test)

print("resilt:")
print(resilt)










