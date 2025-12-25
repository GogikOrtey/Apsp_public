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

main_task = """
Найти, в каком файле говорится про презентацию
Название файла поместить в file_name, его содержание - в file_content
"""

"""

Нужно:
- Проверить, что работает
- Проверить, что инструмнты из PL подгружаются в описание
- Что агент может использовать эти инструменты
- Дать ему задачу на пару шагов для PL
- ОК

- Надо будет проверить, что инструменты из PL корректно собираются как описание, и агент может их использовать
    - Сделать простой тестовый план, что бы он перешёл на страницу https://makitaclub.ru и положил в fills в result номер кода ответа от перехода, а также кол-во вхождений слова "makita" на странице

"""



main_plan = {
    "status": "not_started",
    "current_step": 0,
    "steps": [
        {
            "step_id": 1,
            "goal": "Определить, в каком файле упоминается презентация, и извлечь из него имя и полное содержание.",
            "fills": [
                "file_name",
                "file_content"
            ],
            "status": "pending"
        }
    ]
}

# Схема результата
main_result_schema = {
    "file_name": {
        "type": "string",
        "required": True,
        "description": "Имя файла"
    },
    "file_content": {
        "type": "string",
        "required": True,
        "description": "Содержимое файла"
    }
}

# Шаблон результата, который агент заполняет в процессе работы
main_result_template = {
    "file_name": None,
    "file_content": None
}




resulr_answer = orchestrate(
    task = main_task,
    max_steps = 40,
    result_schema = main_result_schema,
    result_template = main_result_template,
    plan = main_plan
) 

result_task = get_result()
print("result_task:")
print(result_task)