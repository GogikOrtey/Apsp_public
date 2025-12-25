"""
Тут тестирую запуск агента, не из его основного файла
А также с использованием инструментов Playwright
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







# main_task = """ 
# Тебе нужно сделать:

# Перейти на страницу https://makitaclub.ru
# И положить в поля результата номер кода ответа от перехода на эту страницу (в поле url_open_code), а также кол-во вхождений слова "makita" на странице, результат положи в поле count_includes_string

# """


main_task = """ 
Алгоритм, что тебе нужно сделать:

1. Выбрать селектор (используя данные из поля search_input_selectors из input_data), проверить что он даёт результат на странице (инструмент find_elements)
2. Получить окружающий html код вокруг этого элемента, убедиться что это действительно поле ввода запроса на поиск (инструмент get_html_frame)
3. Использовать инструмент наведения фокуса на этот элемент (это smart_focus)
4. Использовать инструмент вставки значений в это поле (запроса из семантики, это значение из поля semantics из input_data), это human_like_input

После вставки текста в поле ввода
5. Сохранить текущий URL страницы (get_current_url) - можешь записать его в memory
6. Нажими Enter (press_enter)
7. Дождись редиректа (wait_for_navigation_or_content)
Если редирект успешен, то запиши в result в поле second_html - URL страницы на которую был совершён переход.

Если редиректа не было в указанный таймаут после нажатия Enter, то попробуй нажать кнопку запуска поиска (элемент из search_button_selectors из input_data). Инструмент smart_focus - нужен только для поля ввода, его не следует использовать для кнопки запуска поиска. Для клика по элементу можно использовать click_element
- Если ничего не происходит 
    пометь текущую пару (input_selector, button_selector) как нерабочую в memory
    если есть ещё неиспользованные селекторы:
        page_restart
        перейти к шагу 1
    иначе:
        FAILED с результатом, что не удалось найти рабочих селекторов поля поиска, и не получилось добиться перехода на следующую страницу.
- Возможно стоит попробовать другие селекторы search_input_selectors и search_button_selectors. Для этого ты можешь перезагрузить текущую страницу (page_restart), и начать алгоритм заново, с выбора селектора, но уже теперь в memory сохрани что первый селектор - не сработал как надо, и стоит попробовать второй

Задача успешно завершится, когда ты заполнишь поле second_html в result.
Если не указано иного, то выбирай первые элементы из массивов в input_data.

"""









# # main_task = """
# # Найти, в каком файле говорится про презентацию
# # Название файла поместить в file_name, его содержание - в file_content
# # """


# # main_plan = {
# #     "status": "not_started",
# #     "current_step": 0,
# #     "steps": [
# #         {
# #             "step_id": 1,
# #             "goal": "Определить, в каком файле упоминается презентация, и извлечь из него имя и полное содержание.",
# #             "fills": [
# #                 "file_name",
# #                 "file_content"
# #             ],
# #             "status": "pending"
# #         }
# #     ]
# # }

# # # Схема результата
# # main_result_schema = {
# #     "file_name": {
# #         "type": "string",
# #         "required": True,
# #         "description": "Имя файла"
# #     },
# #     "file_content": {
# #         "type": "string",
# #         "required": True,
# #         "description": "Содержимое файла"
# #     }
# # }

# # # Шаблон результата, который агент заполняет в процессе работы
# # main_result_template = {
# #     "file_name": None,
# #     "file_content": None
# # }

# # Схема результата
# main_result_schema = {
#     "url_open_code": {
#         "type": "string",
#         "required": True,
#         "description": "Номер кода ответа от перехода на эту страницу"
#     },
#     "count_includes_string": {
#         "type": "string",
#         "required": True,
#         "description": "Кол-во вхождений слова \"makita\" на странице"
#     }
# }

# # Шаблон результата, который агент заполняет в процессе работы
# main_result_template = {
#     "url_open_code": None,
#     "count_includes_string": None
# }



# Схема результата
main_result_schema = {
    "used_seletor_search_input": {
        "type": "string",
        "required": True,
        "description": "Использованный селектор для поля ввода поискового запроса"
    },
    "used_seletor_search_button": {
        "type": "string",
        "required": False,
        "description": "Использованный селектор для кнопки старта поиска"
    },
    "used_search_request": {
        "type": "string",
        "required": True,
        "description": "Использованный поисковый запрос из семантики"
    },
    "second_html": {
        "type": "string",
        "required": True,
        "description": "URL страницы на которую был совершён переход, после запуска поиска"
    }
}

# Шаблон результата, который агент заполняет в процессе работы
main_result_template = {
    "used_seletor_search_input": None,
    "used_seletor_search_button": None,
    "used_search_request": None,
    "second_html": None
}


# Запускаю браузер с видимым окном
launch_browser(headless = False)

resulr_answer = orchestrate(
    task = main_task,
    max_steps = 40,
    result_schema = main_result_schema,
    result_template = main_result_template,
    # plan = main_plan
) 

result_task = get_result()
print("result_task:")
print(result_task)