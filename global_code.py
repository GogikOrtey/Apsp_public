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





# Сохраняет результирующий код парсера в файл
def result_file_JS(result_selectors, host):
    # Собираем название для файла парсера

    # Как нужно чистим домен
    parser_file_name = host.split("://")[1].split("/")[0]
    parser_file_name = parser_file_name.replace("www.", "")
    parser_file_name = parser_file_name.replace(".", "").replace("-", "")
    # TODO регионы потом удалять, но это сильно позже

    base_name_part = "JS_Base_" + parser_file_name
    print(base_name_part)

    # parse_card_code = selector_checker_and_parseCard_gen(result_selectors, data_input_table)












# # result_file_JS(result_selectors, "https://megapteka.ru/basket")
# result_file_JS(result_selectors, "https://www.perekrestok.ru/cat/")



"""

Такие описания будут у ошибок:

const name = $('h1.title-black').text().replace(/\s+/g, ' ').trim()
const article = $('.extended-characteristic > table tr:contains("Артикул") > td').eq(1).text().trim()
const product_id = $('.extended-characteristic > table tr:contains("Код") > td').eq(1).text().trim()
const brand = $('.extended-characteristic > table tr:contains("Бренд") > td').eq(1).text().trim()
const imageLink = "" // [Ошибка генерации APSP]: Селектор не был найден на странице

* Т.е. проверить, если хотя бы в одном наборе данных было задано значение для поиска этого селектора
  и мы его не нашли - то оставлять такую ошибку
    * Если это важный селектр (name, price, ...), то оставляем как критическую ошибку
      а если нет, то как ошибку-предупреждение, которую всё равно нужно будет исправить программисту вручную
      TODO Но позже надо будет подключить агента к решению этой проблемы - примеров у меня ещё пока что нет

Или более критичная:

// [Ошибка генерации APSP]: Не удалось сгенерировать parseCard
/* Описание ошибки:
    Все запросы к селекторам выдали ошибку
*/


Все ошибки хранятся в глобальной массиве message_global


А в конце будет пометка, что это сегнерированный код. Например, такая:

// Код сгенерирован APSP v1.4 
// Дата: 4 дек 2025
// © BrandPol



* Добавить плашку о том, что тестирование кода, а также линтер - ещё не добавлены в проект
  и что правильность кода и отсутствие ошибок нужно на текущий момент проверить самостоятельно
    * А также что нет модуля, который проверят парсер через АПарсер

"""