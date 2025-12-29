""" 
Обработка дигинетики и любых других кастомных запросов на PP 

Полностью генерит код PP
И использует инструменты его проверки в песочнице
А также инструменты работы с запросами в Playwright
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




MAIN_TASK = """

ЗАДАЧА:

Нужно проверить, 

"""