""" 
Здесь будет реализация алгоритма работы агента для 4го шага
"""

""" 

############ Добавить с какого запроса выдача

"""

main_task_all = """

Сейчас в браузере Playwright открыта страница результатов товаров с поисковой выдачи по запросу {}.
Во входных данных (input_data) тебе даны селекторы на элементы этой страницы. Они понадобятся тебе в ходе выполнения проверок и решения задачи. В каждом массиве есть input_data по 3 селектора, из них первый - это самый стабильный и предпочтительный, по умолчанию используй его. Но если вдруг первый окажется по каким-то причинам неподходящим или нерабочим, то есть ещё 2 запасных селектора, которые указывают также на этот элемент.


———————————————————————— Фаза 1 - product

Тебе нужно:

Проверить и выбрать селектор для ссылки на товар. Селектор лежит в поле product_link_selectors во входных данных.
Этот селектор указывает не на весь блок товара, с описанием, ценой и прочим - а только на ссылку, которая далее ведёт на страницу с этим товаром.

Алгоритм: 

1. Проверить, что на текущей странице есть элементы по этому селектору (используя инструмент find_elements). Обычно на странице 12, 16, 24, 36, 48, 64, или примерно такое количество товаров. Если результатов у этого селектора товара меньше 10 или больше 80, то скорее всего он неверный.

В result запиши количество товаров на странице найденных по селектору, в поле count_of_product_on_this_page.

2. Далее - просмотри структуру элемента товара. Это можно сделать удобным инструментом parse_product_blocks_on_current_page. Он вернёт тебе структурные блоки 2го и 3го по счёту товаров на странице, достаточно передать ему селектор, который ты сейчас проверяешь, из поля product_link_selectors. Иногда инструмент parse_product_blocks_on_current_page может отработать некорректно, тогда используй универсальную функцию get_html_frame_on_current_page. В ней можно расширить окно контекста при необходимости. Также помни, что селектор product_link_selectors указывает не на весь блок товара на странице, а только на ссылку на этот товар.

Запиши html структуру одного из товаров в memory, пригодится в будущем.

Когда получишь блок товара, посмотри и убедись, что в нём как минимум есть название. Чаще всего там также есть цена, кнопка "В корзину", "Купить" и подобные, изображение, и иногда краткое описание или характеристики товара. 

Когда корректный селектор товара будет найден - запиши его в поле product_selector в result.

3. Затем нужно посмотреть, будет ли нужна дополнительная обработка значения ссылки на товар, что бы она стала валидной ссылкой. Достаточно часто сайты хранят на товары ссылки без хоста, например в таком виде: href="/products/831271-6/". Тогда нужно будет добавлять хост (напрмиер HOST = "https://example.com")

Если доп. обработка нужна, то попробуй составить валидную ссылку на товар, и проверить её через инструмент check_url_status. Если он вернёт корректный ответ, то собранная ссылка валидна. 
Запиши в result в поле additional_processing_for_the_link_value значение true, если доп. обработка нужна, и значение false, если селектором извлекается сразу валидная ссылка. Если извлекается сразу валидная ссылка, то можно её не проверять через инструмент check_url_status.

4. Нужно составить корректный фрагмент кода, который будет по селектору извлекать ссылку на товар.
На основе результатов предыдущих шагов (значений, которые записаны в result), составь фрагмент кода, формата:

let HOST = "https://example.com"
let products = $('.products-selector')
let product = products?.eq(0)
let link = HOST + $(product)?.attr('href')
console.log("link = " + link)

Это код на JS с использованием cheerio. В нём:
- Вместо .products-selector - укажи текущий селектор товара из поля product_selector в result
- Если требуется добавлять HOST перед ссылкой, то укажи его верное значение. Если не требуется - то убери строчку let HOST = ... и не используй его в let link = ...
- В строке let link = ... нужно будет прописать код, который извлечёт верное значение ссылки на товар, и если это нужно, добавь доп. обработки, что бы в итоге в поле link получилась валидная ссылка на этот товар.

Не добавляй дополнительных строчек без необходимости. В контексте проверки, инициализация объекта сheerio уже будет произведена выше, тебе не нужно добавлять её в этот фрагмент кода.

Сформируй и сохрани этот фрагмент кода в result в поле code_product_processing.

Далее тебе нужно будет проверить, что этот фрагмент кода запускается корректно в среде JS, и корректно обрабатывает и печатает ссылку на первый товар на текущей странице. Для этого используй инструмент get_product_link_on_current_page_cheerio_code. 

Когда проверка будет успешна - запиши в result в поле check_generated_code_successful значение true и заверши задание, отправив DONE.

"""























""" 
result_template:
{
    count_of_product_on_this_page: "",
    product_selector: "",
    additional_processing_for_the_link_value: false,
    code_product_processing: "",
    check_generated_code_successful: true
}
"""











# Пример: 
""" 
{
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
    "last_page_number_displayed": true
}
"""