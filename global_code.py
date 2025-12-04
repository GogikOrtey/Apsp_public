### В этом скрипте собираются все фрагменты кода

# Вынесенные отдельно функции
from addedFunc import *
from gen_data_input_table import data_input_table # Входные данные
from extracting_selector_from_html import * 

# Подключение всех библиотек
from import_all_libraries import * 


"""

Такие описания будут у ошибок:

const name = $('h1.title-black').text().replace(/\s+/g, ' ').trim()
const article = $('.extended-characteristic > table tr:contains("Артикул") > td').eq(1).text().trim()
const product_id = $('.extended-characteristic > table tr:contains("Код") > td').eq(1).text().trim()
const brand = $('.extended-characteristic > table tr:contains("Бренд") > td').eq(1).text().trim()
const imageLink = "" // [Ошибка генерации APSP]: Селектор не был найден на странице

"""