""" 
Глобальная основная точка входа в проект
Что бы точно её не потерять
"""

from import_all_libraries import *
from new_program.main_processer import *

# Хороший пример:
# link = "https://kotel-nasos.ru/nastennyy-gazovyy-kotel-28-kvt-eca-gerda-28-hm-ng_1/"

# link = "https://makitaclub.ru"
# link = "https://makitatrading.ru"
# link = "https://galleryceramics.ru"
# link = "https://cosmedel.ru"
link = "https://cosmedel.ru"



###### Для тестов:
# result_code = main_processer_base(link) # Оборачивает все ошибки в текстовый вывод (включить для фронта)
result_code = main_processer(link)