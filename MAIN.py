""" 
[Устарело]
Глобальная основная точка входа в проект
Что бы точно её не потерять

Для запуска проекта нужно запустить MAIN_APP.py
И зайти на http://127.0.0.1:5000

Техническая информация по тому как работает проект описана в CLAUDE.md
Для генерации использовался по большей части ChatGPT 5.2 через Cursor


"""

# Утилиты для обновления текста на фронте (main_page_2.html).
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







""" 

https://dev.gogorey.ru/auto_gen_parsers/start
https://dev.gogorey.ru/auto_gen_parsers/main


"""
















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








# Это LEGACY обёртка для запуска main_processer, сейчас не используется при запуске задач.
def main_funk_start_on_front(link, uid=None, task_dir=None, page=None):
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
        Пишем в файл, который показывает фронт (main_page_3 /api/result_code):
        result_code_gen/result/result_code.ts
        """
        try:
            # Пишем туда же, куда пишет успешная генерация (в папку задачи, если она есть).
            from new_program.build_final_code import result_file_JS

            result_file_JS(text, task_dir=task_dir)
            return
        except Exception:
            pass

        # Fallback (legacy): если task_dir не передали или импорт пайплайна упал.
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
        result_code = main_processer(link, uid=uid, task_dir=task_dir, page=page)
    except Exception:
        error_text = f"🟠 Ошибка генерации: 🟠\n\n" + traceback.format_exc()
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