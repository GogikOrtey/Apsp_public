""" 
Здесь будет реализация алгоритма работы агента для 4го шага
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





main_task_all = """
Во входных данных (input_data) тебе даны селекторы на элементы этой страницы. Они понадобятся тебе в ходе выполнения проверок и решения задачи. В каждом массиве есть input_data по 3 селектора, из них первый - это самый стабильный и предпочтительный, по умолчанию используй его. Но если вдруг первый окажется по каким-то причинам неподходящим или нерабочим, то есть ещё два запасных селектора, которые указывают также на этот элемент.

Тебе нужно:

Проверить и выбрать селектор для ссылки на товар. Селектор лежит в поле product_link_selectors во входных данных.
Этот селектор указывает не на весь блок товара, с описанием, ценой и прочим - а только на ссылку, которая далее ведёт на страницу с этим товаром.

Алгоритм: 

1. Проверить, что на текущей странице есть элементы по этому селектору (используя инструмент find_elements). Обычно на странице 12, 16, 24, 36, 48, 64, или примерно такое количество товаров. Если результатов у этого селектора товара меньше 10 или больше 80, то скорее всего он неверный (используй это как эвристику, а не как жёсткое правило).

В result запиши количество товаров на странице найденных по селектору, в поле count_of_product_on_this_page.

2. Далее - просмотри структуру элемента товара. Это можно сделать удобным инструментом parse_product_blocks_on_current_page. Он вернёт тебе структурные блоки 2го и 3го по счёту товаров на странице, достаточно передать ему селектор, который ты сейчас проверяешь, из поля product_link_selectors. Этот инструмент ожидает именно селектор на ссылку товара, и сам пройдётся по дереву DOM и извлечёт полные блоки товаров. Иногда инструмент parse_product_blocks_on_current_page может отработать некорректно, тогда используй универсальную функцию get_html_frame_on_current_page. В ней можно расширить окно контекста при необходимости. Также помни, что селектор product_link_selectors указывает не на весь блок товара на странице, а только на ссылку на этот товар.

Запиши html структуру одного из товаров в memory, пригодится в будущем.

Когда получишь блок товара, посмотри и убедись, что в нём как минимум есть название. Чаще всего там также есть цена, кнопка "В корзину", "Купить" и подобные, изображение, и иногда краткое описание или характеристики товара. 

Выбери один из селекторов из product_link_selectors, который оказался корректным, и запиши его в choose_product_selector в result.

3. Затем нужно посмотреть, будет ли нужна дополнительная обработка значения ссылки на товар, что бы она стала валидной ссылкой. Достаточно часто сайты хранят на товары ссылки без хоста, например в таком виде: href="/products/831271-6/". Тогда нужно будет добавлять хост (например HOST = "https://example.com"). HOST должен быть доменом текущей страницы Playwright (протокол + домен). 

Если доп. обработка нужна, то попробуй составить валидную ссылку на товар, и проверить её через инструмент check_url_status. Если он вернёт корректный ответ, то собранная ссылка является валидной. 
Запиши в result в поле additional_processing_for_the_link_value значение true, если дополнительная обработка нужна, а также сохрани в memory информацию о том, какая конкретно дополнительная обработка требуется (если нужно добавить HOST, то сохрани его в memory). Если селектором извлекается сразу валидная ссылка, то запиши значение false в additional_processing_for_the_link_value, и можно не проверять ссылку через инструмент check_url_status.

4. Нужно составить корректный фрагмент кода, который будет по селектору извлекать ссылку на товар.
На основе результатов предыдущих шагов (значений, которые записаны в result), составь фрагмент кода, формата:

let HOST = "https://example.com"
let products = $('.products-selector')
let product = products?.eq(0)
let link = HOST + $(product)?.attr('href')
console.log("link = " + link)

Это код на JS с использованием cheerio. В нём:
- Вместо .products-selector - укажи текущий селектор товара из поля choose_product_selector в result
- Если требуется добавлять HOST перед ссылкой, то укажи его верное значение. Если не требуется - то убери строчку let HOST = ... и не используй его в let link = ...
- В строке let link = ... нужно будет прописать код, который извлечёт верное значение ссылки на товар, и если это нужно, добавь дополнительной обработки, что бы в итоге в поле link получилась валидная ссылка на этот товар. Т.е. если требуется извлечь другой аттрибут из элемента, например не href а data-href, data-url, a или другие, то пропиши это здесь. 

Не добавляй дополнительных строчек без необходимости. В контексте проверки, инициализация объекта cheerio уже будет произведена выше, тебе не нужно добавлять её в этот фрагмент кода.

Сформируй и сохрани этот фрагмент кода в result в поле builded_code_product_processing.

Далее тебе нужно будет проверить, что этот фрагмент кода запускается корректно в среде JS, и корректно обрабатывает и печатает ссылку на первый товар на текущей странице. Для этого используй инструмент get_product_link_on_current_page_cheerio_code. 

Когда проверка будет успешна - запиши в result в поле check_generated_code_successful значение true и заверши задание, отправив DONE.

Если проверка фрагмента кода показала неудачный результат, то не записывай значение false в поле check_generated_code_successful. В таком случае - пробуй изменить код, и запустить проверку снова. Если код будет требовать изменения, не забудь перезаписать его в result в поле builded_code_product_processing.

————————————————————————
Входные данные (input_data):

"""
















""" 
result_template:
{
    count_of_product_on_this_page: "",
    choose_product_selector: "",
    additional_processing_for_the_link_value: false,
    builded_code_product_processing: "",
    check_generated_code_successful: true
}
"""



# Схема результата
main_result_schema = {
    "count_of_product_on_this_page": {
        "type": "number",
        "required": True,
        "description": "Количество товаров на странице найденных по выбранному селектору товара"
    },
    "choose_product_selector": {
        "type": "string",
        "required": True,
        "description": "Выбранный селектор на ссылку товара"
    },
    "additional_processing_for_the_link_value": {
        "type": "boolean",
        "required": True,
        "description": "Нужна ли доп. обработка для значения ссылки, извлекаемой селектором на ссылку товара"
    },
    "builded_code_product_processing": {
        "type": "string",
        "required": True,
        "description": "Сформированный фрагмент кода обработки ссылок товаров"
    },
    "check_generated_code_successful": {
        "type": "boolean",
        "required": True,
        "description": "Была ли проверка сгенерированного фрагмента кода успешна. Ожидает только записи значения true"
    }
}

# Шаблон результата, который агент заполняет в процессе работы
main_result_template = {
    "count_of_product_on_this_page": None,
    "choose_product_selector": None,
    "additional_processing_for_the_link_value": None,
    "builded_code_product_processing": None,
    "check_generated_code_successful": None
}


main_plan = {
    "steps": [
        {
            "step_id": 1,
            "goal": "Проверить селекторы product_link_selectors на наличие и адекватное количество найденных ссылок товаров на текущей странице; зафиксировать количество найденных элементов по выбранному рабочему селектору.",
            "fills": [
                "count_of_product_on_this_page"
            ]
        },
        {
            "step_id": 2,
            "goal": "Проверить, что найденные элементы действительно являются ссылками внутри полноценных карточек товаров (в карточке есть как минимум название), выбрать корректный селектор ссылки на товар и сохранить HTML-структуру одной карточки товара в память.",
            "fills": [
                "choose_product_selector"
            ]
        },
        {
            "step_id": 3,
            "goal": "Определить, требуется ли дополнительная обработка значения ссылки (например, добавление HOST к относительному href или использование другого атрибута) и зафиксировать это в результате. Если требуется, то записать в memory детали.",
            "fills": [
                "additional_processing_for_the_link_value"
            ]
        },
        {
            "step_id": 4,
            "goal": "Сформировать минимальный JS/cheerio фрагмент кода для извлечения валидной ссылки на первый товар по choose_product_selector с учётом необходимости доп. обработки; сохранить код и подтвердить успешность его проверки в среде выполнения.",
            "fills": [
                "builded_code_product_processing",
                "check_generated_code_successful"
            ]
        }
    ]
}


def agent_step_4_product(input_data, search_request):
    # Приводим input_data к строке
    if isinstance(input_data, str):
        input_data_str = input_data
    else:
        try:
            input_data_str = json.dumps(input_data, ensure_ascii=False, indent=4, default=str)
        except Exception:
            input_data_str = str(input_data)

    task = (
        f"Сейчас в браузере Playwright открыта страница результатов товаров с поисковой выдачи по запросу '{search_request}'." +
        main_task_all + 
        input_data_str)

    resulr_answer = orchestrate(
        task = task,
        max_steps = 40,
        result_schema = main_result_schema,
        result_template = main_result_template,
        plan = main_plan,
        step_by_step_running = False, # Разрешаем агенту работать автоматически
    ) 

    result_task = get_result()
    return result_task





# # Проверка:

# input_data_test = {
#     "search_input_selectors": [
#         "#woocommerce-product-search-field-0",
#         "form.woocommerce-product-search input.search-field[type='search'][name='s']",
#         ".site-search .woocommerce-product-search input.search-field"
#     ],
#     "search_button_selectors": [
#         "form.woocommerce-product-search button[type='submit']",
#         ".site-search form.woocommerce-product-search button",
#         ".widget_product_search form button[type='submit']"
#     ],
#     "total_results_count_selectors": [
#         "p.woocommerce-result-count",
#         ".storefront-sorting > p.woocommerce-result-count",
#         "main#main p.woocommerce-result-count"
#     ],
#     "product_link_selectors": [
#         ".products .product-card a.stretched-link[href*='/products/']",
#         ".products a.stretched-link[href*='/products/']",
#         ".products .card a.stretched-link"
#     ],
#     "pagination_container_selectors": [
#         "nav.woocommerce-pagination",
#         ".storefront-sorting nav.woocommerce-pagination",
#         "ul.page-numbers"
#     ],
#     "pagination_page2_selectors": [
#         "nav.woocommerce-pagination a.page-numbers[href*='/page/2/']",
#         "ul.page-numbers a.page-numbers[href*='/page/2/']",
#         "nav.woocommerce-pagination a.next.page-numbers[href*='/page/2/']"
#     ],
#     "pagination_last_page_selectors": [
#         "nav.woocommerce-pagination ul.page-numbers li:nth-last-child(2) > a.page-numbers",
#         "ul.page-numbers li:nth-last-child(2) > a.page-numbers",
#         "nav.woocommerce-pagination a.page-numbers[href*='/page/']"
#     ],
#     "last_page_number_displayed": "true"
# }

# search_request_test = "инструмент"


# # Запускаю браузер с видимым окном
# launch_browser(headless = False)

# goto_url( 
#     url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
#     wait_until = "load",
#     timeout = 30_000
# )

# resilt = agent_step_4_product(input_data_test, search_request_test)

# print("resilt:")
# print(resilt)
# print("builded_code_product_processing:")
# print(resilt.get("builded_code_product_processing"))