# Подключение всех библиотек
from import_all_libraries import * 
from extracting_selector_from_html import * 
from addedFunc import *
from YandexGPT import *
from urllib.parse import parse_qs, urlparse, urlsplit, urlunsplit
from textwrap import dedent



"""

Парсинг поиска написать реально намного проще
    Даже можно дигинетику далеко на потом оставить (когда научимся открывать внутренний браузер)

Если нет извлечения items в parsePage, то удалить эту логику из parse
Но оставить ко на будущее, который это добавляет

TODO На потом: Проверять, приходят ли данные товара где-либо ещё, кроме html страницы поиска
и если да, то уже задействовать json-парсеры, и геттеры


"""





# Данные с сайта 5
data_input_table = {
    "host": "",
    "links": {

    },
    "search_requests": [
        {
            "query": "Ванна акриловая",
            "url_search_query_page_2": "https://stroytorg812.ru/content/search/?s=&q=%D0%92%D0%B0%D0%BD%D0%BD%D0%B0+%D0%B0%D0%BA%D1%80%D0%B8%D0%BB%D0%BE%D0%B2%D0%B0%D1%8F&PAGEN_1=2",
            "count_of_page_on_pagination": "0",
            # Число последней страницы, если оно отображается в блоке пагинации внизу
            "total_count_of_results": "575",
            # Если нет последней страницы пагинации, то общее кол-во найденых товаров
            "links_items": [
                # Нужно также прописать в тз, что эти поисковые запросы должны содержать больше 2х страниц
                "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_lorena_1_5x0_7_pryamougolnaya_bez_nozhek_panel/",
                "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_1_20kh0_70_standart_120/",
                "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_1_50kh0_70_standart_150/",
                "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_1_60kh0_70_standart_160/",
                "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_1_30kh0_70_ultra_130_/",
            ]
        }
    ]
}



def extract_params(url: str) -> dict:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    return {k: v[0] if len(v) == 1 else v for k, v in params.items()} # Преобразуем [""] → ""


def strip_host(url: str) -> str:
    """
    Возвращает относительный путь URL (path + query + fragment) без схемы и хоста.
    """
    parts = urlsplit(url)
    return urlunsplit(("", "", parts.path, parts.query, parts.fragment))



def generate_parsePage_search_requests(data_input_table):
    set = {}

    # TODO Добавить итерацию по всем элементам search_requests
    current_url = data_input_table["search_requests"][0]["url_search_query_page_2"]
    set["link"] = current_url
    extracted_params_from_url = extract_params(current_url)
    print(extracted_params_from_url)

    # data = {'s': '', 'q': 'Ванна акриловая', 'PAGEN_1': '2'}
    data = extracted_params_from_url

    # Возможные варианты названий параметров поиска и пагинации
    search_param_names = ["q", "query", "search"]
    pagination_param_names = ["page", "p", "PAGEN_1", "PAGEN", "page_num"]
    # TODO Здесь сделать перебор потом по подстрокам, если не будет прямого совпадения
    # TODO И далее, если не нашли - то запрос к ИИ, что бы он определил названия параметров

    # Переменные с найденными названиями параметров
    search_param = None
    pagination_param = None

    # Ищем, какой из параметров присутствует
    for name in search_param_names:
        if name in data:
            search_param = name
            break

    for name in pagination_param_names:
        if name in data:
            pagination_param = name
            break

    # Создаём копию словаря без этих ключей
    data_clean = {
        k: v for k, v in data.items()
        if k not in (search_param, pagination_param)
    }

    print("Параметр поиска:", search_param)
    print("Параметр пагинации:", pagination_param)
    print("Очищенный словарь:", data_clean)

    added_url_params = ""
    for key, value in data_clean.items():
        added_url_params += f'url.searchParams.set("{key}", "{value}")'

    set["search_param"] = search_param
    set["pagination_param"] = pagination_param
    set["added_url_params"] = added_url_params

    # Далее извлекаем хост для поиска

    parsed = urlparse(current_url)
    search_host = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    print("search_host = " + search_host)

    # Хост с протоколом
    host = f"{parsed.scheme}://{parsed.netloc}"

    # Путь без хоста
    path = parsed.path

    print("host:", host)
    print("path:", path)
    
    set["host"] = host
    set["path"] = path

    return set

    #TODO Потом переписать покрасивее тут всё

    

# generate_parsePage_search_requests()






def generate_parsePage(set):
    template_parseCard = Template("""
    async parsePage(set: SetType) {
        let url = new URL(`$${HOST}$hostPatch`)
        url.searchParams.set("$searchQuery", set.query)
        url.searchParams.set("$paginationParams", set.page)
        $addedUrlParams

        const data = await this.makeRequest(url.href)
        const $$ = cheerio.load(data)

        if (set.page === 1) {
            $result_pagination_block_value
            this.debugger.put(`totalPages = $${totalPages}`)
            for (let page = 2; page <= Math.min(totalPages, +this.conf.pagesCount); page++) {
                this.query.add({ ...set, query: set.query, type: "page", page: page, lvl: 1 });
            }
        }

        let items: ResultItem[] = [];
        let products = $$("$productSelector")
        if (products.length == 0) {
            this.logger.put(`По запросу $${set.query} ничего не найдено`)
            throw new NotFoundError()
        }
        products.slice(0, +this.conf.itemsCount).each((i, product) => {
            let link = $finalProductLink
            this.query.add({ ...set, query: link, type: "card", lvl: 1 })
        })
        return items;
    }
    """)

    result = template_parseCard.substitute(
        hostPatch = set["path"],
        searchQuery = set["search_param"],
        paginationParams = set["pagination_param"],
        addedUrlParams = set["added_url_params"],
        
        result_pagination_block_value = set["result_pagination_block"],
        productSelector = set["product_selector"],
        finalProductLink = '$(product)?.attr("href")' # Наверное надо будет проверить, верно ли она извлекается

    )

    print(result)
    return result




def main_generate_parsePage():
    # Тут надо будет как-то обработать, что у нас не 1 пример, а 5

    # Извлекает url параметры поиска и пагинации из вхоящей ссылки
    set = generate_parsePage_search_requests(data_input_table) 

    # Получает страницу
    set["page_html"] = get_html(set["link"]) 

    # print(set["page_html"][:1000])

    current_element = data_input_table["search_requests"][0]

    

    # Извлекаем product_selector
    processed_url_product = strip_host(current_element["links_items"][0])
    product_selector = get_css_selector_from_text_value_element(set["page_html"], processed_url_product, is_exact = False, is_multiply_sel_result = True)
    print("\nproduct_selector = " + product_selector)

    # Проверяем, сколько товаров на этой странице
    tree = html_lx.fromstring(set["page_html"])
    search_elem = tree.cssselect(product_selector)
    len_of_products_on_this_page = len(search_elem)
    print(f"len_of_products_on_this_page = {len_of_products_on_this_page}")


    # for elem in search_elem:
    #     print(html_lx.tostring(elem, encoding='unicode', pretty_print=True))

    #     ############ Остановился тут, надо выписать получение всех ссылок
    #     # в данном случае они без хоста, это также учесть
    #     # и проверить, что все (или 80%) ссылок из этой страницы есть в тех что пришли в задаче







    # Вот тут проверить, если элементов меньше 6, то скорее всего селектор неверный
    
    
    

    
    # Извлекаем селектор для пагинации
    if(current_element["count_of_page_on_pagination"]) != "0":
        print("Извлекаем селектор кол-ва страниц")

        result_pagination_block = "" #######
    else:
        print("Извлекаем селектор кол-ва товаров по запросу")

        finding_element = current_element["total_count_of_results"]
        
        pagination_selector = get_css_selector_from_text_value_element(set["page_html"], finding_element, is_exact = False)
        print("pagination_selector: " )
        print(pagination_selector)

        # Проверяем, что селектор не пустой
        if not pagination_selector or pagination_selector.strip() == "":
            raise ErrorHandler("Ошибка: не удалось найти селектор для элемента пагинации!")

        # Проверяем, получаем ли мы по селектору именно нужный элемент
        checked_selector = get_element_from_selector(set["page_html"], pagination_selector)
        print("Проверили, и нашли такой элемент по найденному селектору: " + checked_selector)

        if(finding_element == checked_selector):
            print("Селектор корректен")
            extracting_pagination_1 = f'let totalItems = $("{pagination_selector}")?.first()?.text()?.trim()'
        elif(checked_selector == ""):
            raise ErrorHandler("Ошибка, элемент числа товаров для пагинации не найден по селектору!")
        else:
            print("Нужное значение и извлекаемый элемент совпадают неточно, запускаю AI")
            js_code_extract_pagination = f'let totalItems = $("{pagination_selector}")?.first()?.text()?.trim()'
            print("js_code_extract_pagination = " + js_code_extract_pagination)
            
            request_AI = dedent(
                f"""
                Есть такой код на JS: 
                {js_code_extract_pagination}
                Однако он извлекает "{checked_selector}"
                А должен извлекать: "{finding_element}"
                Измени исходный код, что бы он делал это.
                """
            ).strip()
            # print(request_AI)
            extracting_pagination_1 = send_message_to_AI_agent(request_AI)
            # Значение len_of_products_on_this_page проверяю и валидирую выше (если нет, то кидаю ошибку)
            extracting_pagination_2 = f'let totalPages = Math.ceil(+totalItems / {len_of_products_on_this_page})'
            
            result_pagination_block = extracting_pagination_1 + "\n" + extracting_pagination_2

        # На этом этапе мы получили первую строку, которая извлекает количество товаров на одной странице
        # Далее, нам нужно проверить, сколько элементов подгружается на странице
        # И для этого, нам нужно извлечь селектор, который указывает на товар
        # (а точнее на ссылку на товар)

    # print("result_pagination_block = \n\n" + result_pagination_block) 

    set["result_pagination_block"] = result_pagination_block
    set["product_selector"] = product_selector

    generate_parsePage(set)





    ######################
    # В целом, кажется всё работает
    # Нужно прописать ветку извлечения пагинации с количеством страниц
    # И добавить обработчик, что бы он проверял, находятся ли товары на этих местах





    # Извлекает селектор для товара

    # Добавить обработчик для finalProductLink
        # чаще всего там будет просто '$(product)?.attr("href")', но надо будет проверять, что это работает

    # # Генерирует итоговый кусок кода parsePage
    # generate_parsePage(set)





main_generate_parsePage()


















































# ctrl+L - добавить в чат
# ctrl+K - быстрое исправление локальным чатом