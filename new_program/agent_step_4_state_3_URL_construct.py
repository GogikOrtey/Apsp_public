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

———————————————————————— Фаза 1:

Определить, какие значения в URL отвечают за указание страницы и указание поискового запроса, и составить код позволяющий задавать произвольный запрос и страницу.

Алгоритм:

1. Сохрани текущий URL страницы в result в поле start_page_url. Его можно получить инструментом get_current_url

2. Найди на текущей странице элемент, по нажатию на который будет выполнен переход на 2ю страницу. Его селектор должен лежать в поле pagination_page2_selectors в input_data. Нажми на него (инструмент click_element), затем дождись перехода (инструмент wait_for_navigation_or_content). 

Если перехода не произошло, изучи подробнее окружение элемента pagination_page2_selectors, используя инструмент get_html_frame_on_current_page, либо попробуй два других запасных селектора. Если перехода не происходит и страница не меняется - возвращай FAILED.

Когда переход произойдёт, зафиксируй новый URL в result в поле url_for_2_page.

———————————————————————— Фаза 2:

На основе значений из result:
start_page_url = URL первой страницы
url_for_2_page = URL второй страницы

найди закономерность, как задаётся пагинация.
- Чаще всего она задаётся доп. параметром в URL. Пример: https://kotel-nasos.ru/search/?page=2&query=%D0%BA%D0%BE%D1%82%D0%B5%D0%BB
- Реже, она задаётся внутри пути URL. Пример: https://makitaclub.ru/page/2/?s=инструмент&post_type=product
- Редко пагинация задаётся оффсетом в URL

Если ты видишь, что URL первой страницы и URL второй страницы одинаковы, то возвращай FAILED с сообщением, что товары загружаются доп. запросами.

В этой фазе тебе нужно найти, как именно задаётся пагинация. Если это доп. параметр - то понять, какой параметр за это отвечает (чаще всего это "page", "p", "PAGEN_1" и подобные). Запиши в memory параметр, который по твоему задаёт пагинацию.

Двлее сформируй ссылки на 3ю и 4ю страницы, и проверь их при помощи инструмента check_url_status. Если статус корректен, значит параметр был найден верно. Если нет, то уточняй параметр, и проверь что на странице поиска >= 4 страниц выдачи (просмотрев get_html_frame_on_current_page по селектору pagination_container_selectors).

Когда параметр задания страниц будет найден корректно, зафиксируй эту информацию в свободной форме, в result в поле info_from_page_parameter. На эту информацию ты будешь опираться в будущем, когда будешь собирать код, так что запиши туда нужное достаточное количество информации.

———————————————————————— Фаза 3:

На этой фазе тебе нужно будет найти, где и как задаётся поисковый запрос в URL.

1. Перейди снова на первую страницу. Её URL лежит в result в поле start_page_url

2. Найди на странице поле ввода (это селектор search_input_selectors из input_data). Наведи на него фокус (инструмент smart_focus), и введи второй (или другой) запрос из семантики (объект semantics во входных данных), также проверь, что он отличается от того запроса, по которому был выполнен поиск сейчас: 

###################### selector_product_link

. Для ввода используй инструмент human_like_input. Далее нажми enter (инструмент press_enter) и дождись редиректа (инструмент wait_for_navigation_or_content). Если редиректа не последовало, используй кнопку запуска поиска (селектор search_button_selectors из input_data).

3. Получи текущий URL (инструментом get_current_url). Сравни его с URL первой страницы, который лежит в result в поле start_page_url. Сохрани его в result в поле url_for_second_search_query.

4. На основе различий start_page_url и url_for_second_search_query из result выдели место, где задаётся поисковый запрос. Зафиксируй эту информацию в свободной форме в result в поле info_from_search_query_parameter, запиши туда нужное достаточное количество информации для дальнейшей генерации кода.

———————————————————————— Фаза 4:

В конце, тебе нужно будет сформировать фрагмент кода на JS, который позволит задавать произвольный запрос и указывать произвольную страницу. Код на языке JS.

Мы используем такой синтаксис:

let url = new URL(`${HOST}/search`)
url.searchParams.set("q", set.query)
url.searchParams.set("page", )

В нём мы задаём значения параметров через url.searchParams.set

Значения set.query и set.page будут приходить их кода выше. В них будут заданы параметры: 
- set.query - поисковой запрос
- set.page - страница пагинации

Значение переменной HOST будет инициализировано выше, и 
HOST = #################################
тебе не нужно будет задавать значение для HOST в своём фрагменте кода.

Ориентируйся на значения из result:
- В поле info_from_page_parameter зафиксирована информация, какой параметр или участок URL отвечает за изменение страницы page.
- В поле info_from_search_query_parameter зафиксирована информация, какой параметр или участок URL отвечает за изменение поискового запроса search query.

Чаще всего параметры поиска и текущей страницы задаются в searchParams, но иногда они задаются напрямую в строке URL, в таком случае нужно будет использовать синтаксис с ${}. Также, в исходном URL могут быть заданы дополнительные параметры, которые не влияют на запрос и текущую страницу, все эти параметры нужно будет сохранить.

Значение URL на 2 страницу поиска текущего сайта ты можешь посмотреть в поле url_for_2_page.

Примеры:

- Пример 1:
    Строка на поиск у сайта, на 2ю страницу поиска: 
    https://galen.bg/catalogsearch/result/index/?p=2&q=мл

    Фрагмент с формированием URL:
    let url = new URL(`${HOST}/catalogsearch/result/index/`)
    url.searchParams.set("q", set.query)
    url.searchParams.set("p", set.page)

- Пример 2:
    Строка на поиск у сайта, на 2ю страницу поиска: 
    https://stroytorg812.ru/content/search/?s=&q=Ванна&PAGEN_1=2

    Фрагмент с формированием URL:
    let url = new URL(`${HOST}/content/search/`)
    url.searchParams.set("s", "")
    url.searchParams.set("q", set.query)
    url.searchParams.set("PAGEN_1", set.page)

- Пример 3:
    Строка на поиск у сайта, на 2ю страницу поиска: 
    https://gidro-top.ru/search/Ванна/?page=2

    Фрагмент с формированием URL:
    let url = new URL(`${HOST}/search/${set.query}/`)
    url.searchParams.set('/?page', set.page);

Тебе нужно будет составить только необходимый фрагмент кода на JS, в котором будет формироваться URL с использованием этих параметров. Не добавляй дополнительных строчек в результат кода без необходимости. Помести его в result в поле result_code_url_builder.






















Входные данные:


"""




""" 

{
    "start_page_url"
    "url_for_2_page"
    "info_from_page_parameter"
    "info_from_search_query_parameter"
    "url_for_second_search_query"
    "result_code_url_builder"
}

"""




































def gen_main_task_all(selector_product_link):
    main_task_all = """
Во входных данных (input_data) тебе даны селекторы на элементы этой страницы. Они понадобятся тебе в ходе выполнения проверок и решения задачи. В каждом массиве есть input_data по 3 селектора, из них первый - это самый стабильный и предпочтительный, по умолчанию используй его. Но если вдруг первый окажется по каким-то причинам неподходящим или нерабочим, то есть ещё два запасных селектора, которые указывают также на этот элемент.

Тебе нужно:

Определить способ, как на этой странице получить значение максимального количества страниц выдачи, и написать код который это делает.

Алгоритм:

Сначала просмотри инструментом get_html_frame_on_current_page html код всего блока пагинации (который указан в pagination_container_selectors в input_data). Запиши его в memory.

Шаг 1. Определить, как извлекать значение максимального количества страниц:
1.1 Если поле last_page_number_displayed в input_data = true, это значит что в элементе пагинации, который выполняет переход на последнюю страницу, был замечен текст, в котором записан номер этой последней страницы.

Попробуй запустить инструмент get_total_pages_on_current_page_cheerio с селектором на элементы пагинации. Но чаще всего, селектора указывающего на весь блок пагинации (pagination_container_selectors) недостаточно для того что бы инструмент get_total_pages_on_current_page_cheerio и код который он запускает, корректно сработал. Я рекомендую тебе попробовать добавить к селектору всего блока пагинации - в конце уточняющие части, так что бы он указывал на элементы, содержащие числа пагинации (посмотри по html коду блока пагинации). Чаще всего достаточно добавить в конец селектора например "a", "span", "li" и подобные. Например, если базовый селектор ".paging", попробуй сделать ".paging a" ".paging span", и т.д. При добвлении элементов отдавай приоритет небольшим дополнениям, т.е. не стоит добавлять в селектор ещё 10 элементов, обычно достаточно 1, 2, 3 и редко больше.

Попробуй запустить get_total_pages_on_current_page_cheerio максимум 2 раза (с разными селекторами). Если он выдаёт -Infinity, 0 или другое некорректное значение, то переходи к шагу 1.2. 

Если инструмент get_total_pages_on_current_page_cheerio выдал корректное значение - максимальное количество страниц пагинации на этом сайте, то запиши селектор в result в поле pagination_max_page_value_selector. Также запиши в result в поле type_struct_extract_max_page значение "simple_max", и переходи к шагу 2 - генерации кода.

1.2 Если last_page_number_displayed = true, но 1.1 не дал результата, ИЛИ если last_page_number_displayed = false, то значит номер последней страницы не указан явно текстом, но скорее всего его можно извлечь из ссылки которая находится в элементе перехода на последнюю страницу, либо из другого его атрибута или текста. Селектор этого элемента лежит в pagination_last_page_selectors в input_data.

Получи этот элемент через инструмент get_html_frame_on_current_page, и если в нём действительно есть номер последней страницы, то запиши в result в поле type_struct_extract_max_page значение "extract_from_last_page_element", и в поле pagination_max_page_value_selector запиши селектор, указывающий на этот элемент перехода на последнюю страницу, и переходи к шагу 2 - генерации кода.

1.3 Если last_page_number_displayed в input_data = null, или предыдущие шаги 1.1 и 1.2 не дали результатов, то значит в блоке пагинации нет номера последней страницы. Проверь, если поле total_results_count_selectors в input_data не равняется null, то значит на странице был найден элемент, в котором в тексте есть число общего количества найденных результатов по этому запросу. Значит, мы сможем найти максимальное количество страниц позже, из значения этого элемента. Проверь его через инструмент get_html_frame_on_current_page. Если там указано число найденных элементов (например "По запросу _ найдено 3442 товара"), значит это нужный элемент. 
Запиши в result в поле type_struct_extract_max_page значение "use_total_count", и в поле pagination_max_page_value_selector запиши селектор, указывающий на этот элемент, и переходи к шагу 2 - генерации кода.

Если в этом элементе total_results_count_selectors нет нужного подходящего числа, или вообще не указано текста, или например количество найденных результатов указано текстом ("три тысячи четыреста сорок два"), то это не то что нам нужно. В таком случае проверь остальные два запасных селектора из поля total_results_count_selectors.

Если шаги 1.1, 1.2 и 1.3 не дали результатов, то верни FAILED, с описанием того что не получилось.

————————————————————————

После того как поле type_struct_extract_max_page записано, запрещено менять стратегию.

Шаг 2. Генерация кода

На этом шаге тебе нужно сформировать код (чаще всего одну строку), который будет задавать значение totalPages. Значение должно быть числовым (не строковым)

2.1 Если в result в поле type_struct_extract_max_page указано "simple_max", значит для итогового кода достаточно использовать код: 
"let totalPages = Math.max(...$(selector).get().map(item => +$(item).text().trim()).filter(Boolean))", заменив selector на значение из поля pagination_max_page_value_selector записанного в result. Используй ИМЕННО ЭТУ строку кода, никак не изменяя её, только заменив selector на нужный, т.к. если в поле type_struct_extract_max_page указано "simple_max", то значит на предыдущих шагах уже была проведена проверка этого кода, и он оказался рабочим. Изменяй что-либо в этой строке кроме селектора, только в том случае, если первая попытка проверки через get_total_pages_on_current_page_cheerio_code выдала ошибку, потому что этот код должен работать практически во всех случаях. Преобразование значения в число уже включено в это выражение.

Тогда тебе нужно сформировать эту одну эту строку, и проверить что она корректно работает, используя инструмент get_total_pages_on_current_page_cheerio_code.

После успешной проверки - записать этот код в result в поле builded_code_get_max_page_on_pagination. 
Если проверка неуспешна - то переходи к шагу 2.2, где ты соберёшь нужную строку обработки извлечения значения самостоятельно. 

2.2 Если в result в поле type_struct_extract_max_page указано "extract_from_last_page_element", или на шаге 2.1 была неуспешная проверка, тогда твоя задача написать код, который извлекает числовое значение номера последней страницы из элемента перехода на последнюю страницу (который указан в result в pagination_max_page_value_selector). Приведу несколько примеров, можешь ориентироваться на них:

Если значение текстовое:
let totalPages = +$("h1 > strong").text().trim()
let totalPages = +$('.pagination a')?.eq(-3).text().trim()
let totalPages = +$('.site-main__inner > a[href]')?.eq(-1).text().trim()
let totalPages = +$('.pagination > span').last()?.find('a').text().trim()
let totalPages = +$(".page-nav__nums_desktop > a")?.last().text().trim()

Если извлекается из ссылки, то используй регулярное выражение, например:
Для ссылки "https://kotel-nasos.ru/search/?page=115&query=%D0%BA%D0%BE%D1%82%D0%B5%D0%BB"
подойдёт код:
let totalPages = +$('.pagination a')?.eq(-3)?.attr('href')?.match(/[?&]page=(\d+)/)?.at(1);

Проверь что этот код корректно работает через инструмент get_total_pages_on_current_page_cheerio_code, и запиши его в result в поле builded_code_get_max_page_on_pagination.

2.3 Если в result в поле type_struct_extract_max_page указано "use_total_count", значит нам нужно будет сначала получить число найденных товаров из элемента, указанного в result в поле pagination_max_page_value_selector. 

    2.3.1 Сначала получи количество элементов товара, которые отображаются на одной странице. Используй инструмент find_elements с селектором """ + selector_product_link + """
    так ты получишь count элементов товара на странице. Запиши это значение в memory

    2.3.2 Собрать фрагмент кода. Сначала получаем totalCount
    Тут нам нужно будет сначала получить totalCount из элемента pagination_max_page_value_selector, используя регулярку что бы вытащить именно нужное число количества товаров. 

    Текстовое значение этого элемента может быть например "По запросу _ найдено 3442 товара". Тогда валидный код будет:
    let totalCount = +$("p.result-count").text()?.replace(/\D/g, '');

    Ещё пример:
    Если строка будет "Отображение 1–16 из 1 944", тогда валидный код будет:
    let totalCount = +$("p.result-count").text()?.split("из")?.at(1)?.replace(/\D/g, '');

    2.3.3 Затем добавляем строку получения нужного нам totalPages:

    Если количество отображаемых товаров на странице = 36, тогда код будет:
    let totalPages = Math.ceil(+totalCount / 36)
    Актуальное количество отображаемых на странице товаров для этого сайта, сохранено у тебя в memory.

    В итоге должно получиться 2 строки кода, например:
    let totalCount = +$("p.result-count").text()?.replace(/\D/g, '');
    let totalPages = Math.ceil(+totalCount / 36);

    Проверь что этот код корректно работает через инструмент get_total_pages_on_current_page_cheerio_code, и запиши его в result в поле builded_code_get_max_page_on_pagination. 

————————————————————————

Не добавляй дополнительных строчек в результат кода без необходимости. В контексте проверки, инициализация объекта cheerio уже будет произведена выше, тебе не нужно добавлять её в свой фрагмент кода.

Входные данные:

    """ 

    return main_task_all





# Схема результата
main_result_schema = {
    "pagination_max_page_value_selector": {
        "type": "simple_max | extract_from_last_page_element | use_total_count",
        "required": True,
        "description": "Селектор, указывающий на элемент, из которого мы будем извлекать значение максимального количества страниц для пагинации. Селектор может указывать либо на список элементов пагинации, либо на элемент последней страницы, либо на элемент с totalCount."
    },
    "type_struct_extract_max_page": {
        "type": "string",
        "required": True,
        "description": "Тип структуры кода для извлечения максимального количества страниц для пагинации"
    },
    "builded_code_get_max_page_on_pagination": {
        "type": "string",
        "required": True,
        "description": "Сформированный фрагмент кода извлечения максимального количества страниц для пагинации"
    }
}

# Шаблон результата, который агент заполняет в процессе работы
main_result_template = {
    "pagination_max_page_value_selector": None,
    "type_struct_extract_max_page": None,
    "builded_code_get_max_page_on_pagination": None
}




input_data_test = {
    "search_input_selectors": [
        "#woocommerce-product-search-field-0",
        "form.woocommerce-product-search input.search-field[type='search'][name='s']",
        ".site-search .woocommerce-product-search input.search-field"
    ],
    "search_button_selectors": [
        "form.woocommerce-product-search button[type='submit']",
        ".site-search form.woocommerce-product-search button",
        ".widget_product_search form button[type='submit']"
    ],
    "total_results_count_selectors": [
        "p.woocommerce-result-count",
        ".storefront-sorting > p.woocommerce-result-count",
        "main#main p.woocommerce-result-count"
    ],
    "product_link_selectors": [
        ".products .product-card a.stretched-link[href*='/products/']",
        ".products a.stretched-link[href*='/products/']",
        ".products .card a.stretched-link"
    ],
    "pagination_container_selectors": [
        "nav.woocommerce-pagination",
        ".storefront-sorting nav.woocommerce-pagination",
        "ul.page-numbers"
    ],
    "pagination_page2_selectors": [
        "nav.woocommerce-pagination a.page-numbers[href*='/page/2/']",
        "ul.page-numbers a.page-numbers[href*='/page/2/']",
        "nav.woocommerce-pagination a.next.page-numbers[href*='/page/2/']"
    ],
    "pagination_last_page_selectors": [
        "nav.woocommerce-pagination ul.page-numbers li:nth-last-child(2) > a.page-numbers",
        "ul.page-numbers li:nth-last-child(2) > a.page-numbers",
        "nav.woocommerce-pagination a.page-numbers[href*='/page/']"
    ],
    "last_page_number_displayed": "true"
}






main_plan = {
    "steps": [
        {
            "step_id": 1,
            "goal": "Определить источник/селектор, из которого можно надежно извлечь максимальное количество страниц (числа в элементах пагинации; либо номер в элементе перехода на последнюю страницу; либо totalCount в тексте счетчика результатов). Зафиксировать выбранный тип структуры и селектор.",
            "fills": [
                "type_struct_extract_max_page",
                "pagination_max_page_value_selector"
            ]
        },
        {
            "step_id": 2,
            "goal": "Сформировать итоговый код, который возвращает числовое значение totalPages согласно выбранному типу структуры извлечения. Если выбран тип use_total_count — предварительно определить количество товаров на одной странице. Проверить работоспособность кода инструментом get_total_pages_on_current_page_cheerio_code и зафиксировать результат.",
            "fills": [
                "builded_code_get_max_page_on_pagination"
            ]
        }
    ]
}

###### Добавить семантику!

def agent_step_4_state_3_URL_construct(input_data, search_request, selector_product_link, semantics):
    # Приводим input_data к строке
    if isinstance(input_data, str):
        input_data_str = input_data
    else:
        try:
            input_data_str = json.dumps(input_data, ensure_ascii=False, indent=4, default=str)
        except Exception:
            input_data_str = str(input_data)

    ###################### semantics
    ###################### Значение для переменной HOST

    task = (
        f"Сейчас в браузере Playwright открыта страница результатов товаров с поисковой выдачи по запросу '{search_request}'." +
        gen_main_task_all(selector_product_link) + 
        input_data_str)

    resulr_answer = orchestrate(
        task = task,
        max_steps = 40,
        result_schema = main_result_schema,
        result_template = main_result_template,
        # plan = main_plan,
        # step_by_step_running = False, # Разрешаем агенту работать автоматически
    ) 

    result_task = get_result()
    return result_task





# Проверка:

search_request_test = "инструмент"

# Запускаю браузер с видимым окном
launch_browser(headless = False)

goto_url( 
    url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
    wait_until = "load",
    timeout = 30_000
)

resilt = agent_step_4_state_3_URL_construct(input_data_test, search_request_test, ".products .product-card a.stretched-link[href*='/products/']")

print("resilt:")
print(resilt)
print("builded_code_get_max_page_on_pagination:")
print(resilt.get("builded_code_get_max_page_on_pagination"))