"""
2й шаг генерации parsePage - в котором агент на главной странице сайта, находит по полученному селектору поле ввода поискового запроса и кнопку запуска поиска. Далее фокусируется на поле ввода, вводит туда первый запрос из семантики, и ждёт редиректа на страницу результатов поисковой выдачи

Возвращает использованные селекторы и ссылку на 2ю страницу
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








main_task = """ 
Алгоритм, что тебе нужно сделать:

1. Сохранить текущий URL страницы (get_current_url) - записать его в result в поле first_url
2. Выбрать селектор (используя данные из поля search_input_selectors из input_data), проверить что он даёт результат на странице (инструмент find_elements)
3. Получить окружающий html код вокруг этого элемента, убедиться что это действительно поле ввода запроса на поиск (инструмент get_html_frame)
4. Использовать инструмент наведения фокуса на этот элемент (это smart_focus)
5. Использовать инструмент вставки значений в это поле (запроса из семантики, это значение из поля semantics из input_data), это human_like_input

После вставки текста в поле ввода
6. Нажими Enter (press_enter)
7. Дождись редиректа (wait_for_navigation_or_content), указав в его аргументе old_url - значение из поля first_url из result.
Если редирект успешен, то запиши в result в поле second_html - URL страницы на которую был совершён переход.

Если редиректа не было в указанный таймаут после нажатия Enter, то попробуй нажать кнопку запуска поиска (элемент из search_button_selectors из input_data). Инструмент smart_focus - нужен только для поля ввода, его не следует использовать для кнопки запуска поиска. Для клика по элементу можно использовать click_element
- Если ничего не происходит 
    пометь текущую пару (input_selector, button_selector) как нерабочую в memory
    если есть ещё неиспользованные селекторы:
        page_restart
        перейти к шагу 1 (используя goto_main_plan_step)
    иначе:
        FAILED с результатом, что не удалось найти рабочих селекторов поля поиска, и не получилось добиться перехода на следующую страницу.
- Возможно стоит попробовать другие селекторы search_input_selectors и search_button_selectors. Для этого ты можешь перезагрузить текущую страницу (page_restart), и начать алгоритм заново, с выбора селектора, но уже теперь в memory сохрани что первый селектор - не сработал как надо, и стоит попробовать второй

Задача успешно завершится, когда ты заполнишь поле second_html в result.
Если не указано иного, то выбирай первые элементы из массивов в input_data.

Входные данные:

"""



# Схема результата
main_result_schema = {
    "first_url": {
        "type": "string",
        "required": True,
        "description": "Начальный URL первой страницы"
    },
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
    "first_url": None,
    "used_seletor_search_input": None,
    "used_seletor_search_button": None,
    "used_search_request": None,
    "second_html": None
}


main_plan = {
    "steps": [
        {
            "step_id": 1,
            "goal": "Зафиксировать URL первой страниц, определить рабочий селектор поля ввода поиска и зафиксировать выбранный поисковый запрос из semantics, который будет введён в это поле.",
            "fills": [
                "first_url",
                "used_seletor_search_input",
                "used_search_request"
            ]
        },
        {
            "step_id": 2,
            "goal": "Запустить поиск (Enter или кнопка), при необходимости подобрать рабочий селектор кнопки запуска поиска и зафиксировать URL страницы, на которую произошёл переход после запуска поиска.",
            "fills": [
                "used_seletor_search_button",
                "second_html"
            ]
        }
    ]
}


def use_agent_for_step_2_gen_parsePage(input_data, *, uid: str | None = None, task_dir: str | Path | None = None):
    # Приводим input_data к строке
    if isinstance(input_data, str):
        input_data_str = input_data
    else:
        try:
            input_data_str = json.dumps(input_data, ensure_ascii=False, indent=4, default=str)
        except Exception:
            input_data_str = str(input_data)

    task = main_task + input_data_str

    resulr_answer = orchestrate(
        task = task,
        max_steps = 40,
        result_schema = main_result_schema,
        result_template = main_result_template,
        plan = main_plan,
        step_by_step_running = False, # Разрешаем агенту работать автоматически
        uid = uid,
        task_dir = task_dir,
    ) 

    result_task = get_result()
    return result_task


# print("result_task:")
# print(result_task)