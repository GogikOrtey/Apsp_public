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
import traceback
from pathlib import Path

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
    # print("Фронтовская функция запущена, link = " + link)
    # # Ленивая загрузка тяжёлых импортов, чтобы импорт MAIN.py был безопасным.
    # from new_program.main_processer import main_processer_base
    # return main_processer_base(link)

    # time.sleep(5) 

    # update_content_front_reasoning("Думаю о мороженом")

    # for i in range(0, 50):
    #     print(f"test log {i}")

    # # Запускаю браузер с видимым окном
    # launch_browser(headless = False)

    # goto_url( 
    #     url = "https://makitaclub.ru/",
    #     wait_until = "load",
    #     timeout = 30_000
    # )

    # time.sleep(10) 
    # print("Завершено")

    def _write_error_to_result_code_ts(text: str) -> None:
        """
        Пишем в файл, который показывает фронт (new_page_3 /api/result_code):
        result_code_gen/result/result_code.ts
        """
        try:
            target = Path(__file__).resolve().parent / "result_code_gen" / "result" / "result_code.ts"
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(target)
        except Exception:
            # Если даже запись результата упала — не даём падать main_funk_start_on_front наружу.
            pass

    try:
        result_code = main_processer(link)
    except Exception:
        error_text = f"🟠 Ошибка генерации: 🟠\n" + traceback.format_exc()
        _write_error_to_result_code_ts(error_text)
        return error_text

    print("Генерация завершена")
    time.sleep(5) 
    return result_code
    


# if __name__ == "__main__":
#     # Пример ручного запуска:
#     link = "https://makitaclub.ru"
#     result_code = main_funk_start_on_front(link)
#     print(result_code)