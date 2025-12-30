""" 
Глобальная основная точка входа в проект
Что бы точно её не потерять
"""

# from import_all_libraries import *
# from new_program.main_processer import *

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


if __name__ == "__main__":
    # Пример ручного запуска:
    link = "https://makitaclub.ru"
    result_code = main_funk_start_on_front(link)
    print(result_code)