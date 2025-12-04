### В этом скрипте собираются все фрагменты кода

# Вынесенные отдельно функции
from addedFunc import *
from gen_data_input_table import data_input_table # Входные данные
from extracting_selector_from_html import * 

# Подключение всех библиотек
from import_all_libraries import * 




# Тут будет шаблон основного кода

# Получаем базовые переменные - список полей, название парсера, хост

# Получаем и проверяем на корректность входной массив
    # В будущем на этом шаге можно будет его по частям автоматически собирать

# Генерируем parseCard

# Генерируем parsePage

# Генерируем makeRequest

# Вставляем это всё в основной шаблон

# Далее проходимся автоформаттером

# И затем, проверка линтером (на синтаксические ошибки)

# После этого можно уже возвращать готовый результат


"""

Такие описания будут у ошибок:

const name = $('h1.title-black').text().replace(/\s+/g, ' ').trim()
const article = $('.extended-characteristic > table tr:contains("Артикул") > td').eq(1).text().trim()
const product_id = $('.extended-characteristic > table tr:contains("Код") > td').eq(1).text().trim()
const brand = $('.extended-characteristic > table tr:contains("Бренд") > td').eq(1).text().trim()
const imageLink = "" // [Ошибка генерации APSP]: Селектор не был найден на странице

Или более критичная:

// [Ошибка генерации APSP]: Не удалось сгенерировать parseCard
/* Описание ошибки:
    Все запросы к селекторам выдали ошибку
*/

"""