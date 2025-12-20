# Собираю нового полнофункционального агента

#region Импорты
# Чтобы при запуске файла из этой папки были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import os
import json
from typing import Any
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT

# Подключаю инструменты
from reasoning_agent.agent_tools import *


#region Переменная для хранения задачи

main_task = """
Найти, в каком файле идёт речь про презентацию
"""

HISTORY_WINDOW = 10  # сколько последних шагов отдаём в LLM
MAX_STEPS = 20 # Максимальное количество шагов агента для решения задачи

#region Описание инструментов - их аннотация

#region Реализация инструментов

#region Системный промпт

#region Формирование запроса шага

#region Контракт ответа шага

#region Обработчик хранения памяти

#region Орекстратор