""" 
Глобальная основная точка входа в проект
Что бы точно её не потерять
"""

# Утилиты для обновления текста на фронте (new_page_2.html).
# Важно: сами функции "молча" игнорируют ошибки соединения (если фронт не запущен).
from front_client import (
    update_content_front_reasoning,
    update_content_front_goal,
    update_content_front_action,
    update_content_front_update_result,
    update_content_front_last_phase_result,
)

import time

from import_all_libraries import *
from new_program.main_processer import *

# Хороший пример:
# link = "https://kotel-nasos.ru/nastennyy-gazovyy-kotel-28-kvt-eca-gerda-28-hm-ng_1/"

# link = "https://makitaclub.ru"
# link = "https://cosmedel.ru"
# link = "https://domo-terra.ru/"
# link = "https://domplitok.ru"
# link = "https://makitatrading.ru"
# link = "https://galleryceramics.ru"
# link = "http://systemarf.ru/"



###### Для тестов:
# result_code = main_processer_base(link) # Оборачивает все ошибки в текстовый вывод (включить для фронта)
# result_code = main_processer(link) 


def main_funk_start_on_front(link):
    print("Фронтовская функция запущена, link = " + link)
    # # Ленивая загрузка тяжёлых импортов, чтобы импорт MAIN.py был безопасным.
    # from new_program.main_processer import main_processer_base
    # return main_processer_base(link)

    time.sleep(5) 

    update_content_front_reasoning("Думаю о мороженом")

    for i in range(0, 50):
        print(f"test log {i}")

    # Запускаю браузер с видимым окном
    launch_browser(headless = False)

    goto_url( 
        url = "https://makitaclub.ru/",
        wait_until = "load",
        timeout = 30_000
    )

    # Скриншоты пушатся автоматически внутри launch_browser() (см. playwright_tool/browser_start.py).

    # time.sleep(10) 
    # print("Завершено")


# if __name__ == "__main__":
#     # Пример ручного запуска:
#     link = "https://makitaclub.ru"
#     result_code = main_funk_start_on_front(link)
#     print(result_code)