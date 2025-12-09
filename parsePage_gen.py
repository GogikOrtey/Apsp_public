# Подключение всех библиотек
from import_all_libraries import * 
from extracting_selector_from_html import * 
from gen_data_input_table import data_input_table # Входные данные
from addedFunc import *
from YandexGPT import *





this_module_title = """


--------------------------------------------------------------------------------------------------

                                       EXTRACTION SELECTOR

--------------------------------------------------------------------------------------------------

"""




#TODO Потом интегрировать это в вынесенный файл с данными

# # Данные с сайта 5
# data_input_table = {
#     "host": "",
#     "links": {

#     },
#     "search_requests": [
#         {
#             "query": "Ванна акриловая",
#             "url_search_query_page_2": "https://stroytorg812.ru/content/search/?s=&q=%D0%92%D0%B0%D0%BD%D0%BD%D0%B0+%D0%B0%D0%BA%D1%80%D0%B8%D0%BB%D0%BE%D0%B2%D0%B0%D1%8F&PAGEN_1=2",
#             "count_of_page_on_pagination": "0",
#             # Число последней страницы, если оно отображается в блоке пагинации внизу
#             "total_count_of_results": "576",
#             # Если нет последней страницы пагинации, то общее кол-во найденых товаров
#             "links_items": [
#                 # Нужно также прописать в тз, что эти поисковые запросы должны содержать больше 2х страниц
#                 "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_lorena_1_5x0_7_pryamougolnaya_bez_nozhek_panel/",
#                 "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_1_20kh0_70_standart_120/",
#                 "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_1_50kh0_70_standart_150/",
#                 "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_1_60kh0_70_standart_160/",
#                 "https://stroytorg812.ru/catalog/vanny/vanna_akrilovaya_1_30kh0_70_ultra_130_/",
#             ]
#         }
#     ],
#     "timestamp": 1764753782
# }

# # Данные с сайта 1
# data_input_table = {
#     "host": "",
#     "links": {

#     },
#     "search_requests": [
#         {
#             "query": "Ванна",
#             "url_search_query_page_2": "https://vodomirural.ru/search/?tags=&how=r&q=%D0%92%D0%B0%D0%BD%D0%BD%D0%B0&PAGEN_1=2",
#             "count_of_page_on_pagination": "6",
#             # Число последней страницы, если оно отображается в блоке пагинации внизу
#             "total_count_of_results": "0",
#             # Если нет последней страницы пагинации, то общее кол-во найденых товаров
#             "links_items": [
#                 # Нужно также прописать в тз, что эти поисковые запросы должны содержать больше 2х страниц
#                 "https://vodomirural.ru/catalog/vanny_stalnye_i_aksessuary_k_nim/33951/?sphrase_id=4108852",
#                 "https://vodomirural.ru/catalog/vanny_stalnye_i_aksessuary_k_nim/33945/?sphrase_id=4108852",
#                 "https://vodomirural.ru/catalog/vanny_stalnye_i_aksessuary_k_nim/41341/?sphrase_id=4108852",
#             ]
#         }
#     ],
#     "timestamp": 1764753782
# }


#TODO У сайта 3 нет пагинации вообще, при поиске
# Надо найти кол-во найденных товаров
# И сверить с кол-вом товаров на странице
# И если при какой-то галочке, то пропускаем 


# # Данные с сайта 2
# #TODO Здесь надо внедрять установку оффсета
# # Проверять, если явной пагинации нет, но оффсет есть - то выислять разницу между 2 и 3й страницами
# # и привязывать его к пагинации
# data_input_table = {
#     "host": "",
#     "links": {

#     },
#     "search_requests": [
#         {
#             "query": "Ванна",
#             "url_search_query_page_2": "https://santehnica-vodoley.ru/search/?find=%D0%92%D0%B0%D0%BD%D0%BD%D0%B0&curPos=24",
#             "url_search_query_page_3": "https://santehnica-vodoley.ru/search/?find=%D0%92%D0%B0%D0%BD%D0%BD%D0%B0&curPos=48",
#             "count_of_page_on_pagination": "6",
#             # Число последней страницы, если оно отображается в блоке пагинации внизу
#             "total_count_of_results": "0",
#             # Если нет последней страницы пагинации, то общее кол-во найденых товаров
#             "links_items": [
#                 # Нужно также прописать в тз, что эти поисковые запросы должны содержать больше 2х страниц
#                 "https://vodomirural.ru/catalog/vanny_stalnye_i_aksessuary_k_nim/33951/?sphrase_id=4108852",
#                 "https://vodomirural.ru/catalog/vanny_stalnye_i_aksessuary_k_nim/33945/?sphrase_id=4108852",
#                 "https://vodomirural.ru/catalog/vanny_stalnye_i_aksessuary_k_nim/41341/?sphrase_id=4108852",
#             ]
#         }
#     ],
#     "timestamp": 1764872654
# }

# # Данные с сайта 4
# data_input_table = {
#     "host": "",
#     "links": {

#     },
#     "search_requests": [
#         {
#             "query": "Ванна",
#             "url_search_query_page_2": "https://kotel-nasos.ru/search/?page=2&query=%D0%9A%D0%BE%D1%82%D1%91%D0%BB",
#             "count_of_page_on_pagination": "115",
#             "total_count_of_results": "0",
#             "links_items": [
#                 "https://kotel-nasos.ru/elektricheskiy-kotel-evan-epo-pro-54/",
#                 "https://kotel-nasos.ru/elektricheskiy-kotel-evan-epo-pro-48/",
#                 "https://kotel-nasos.ru/elektricheskiy-kotel-evan-epo-pro-42/",
#             ]
#         }
#     ],
#     "timestamp": 1764839602
# }

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

# region Extract URL
def generate_parsePage_search_requests(data_input_table):
    set_item = {}

    # TODO Добавить итерацию по всем элементам search_requests
    current_url = data_input_table["search_requests"][0]["url_search_query_page_2"]
    set_item["link"] = current_url
    extracted_params_from_url = extract_params(current_url)
    print(extracted_params_from_url)

    # data = {'s': '', 'q': 'Ванна акриловая', 'PAGEN_1': '2'}
    data = extracted_params_from_url

    # Возможные варианты названий параметров поиска и пагинации
    search_param_names = ["q", "query", "search", "find"]
    pagination_param_names = ["page", "p", "PAGEN_1", "PAGEN", "page_num"]

    # Переменные с найденными названиями параметров
    search_param = None
    pagination_param = None

    #TODO Потом ещё дополнительно тестировать это, и на других сайтах

    # Ищем, какой из параметров присутствует, по прямому совпадению
    for name in search_param_names:
        if name in data:
            search_param = name
            break

    for name in pagination_param_names:
        if name in data:
            pagination_param = name
            break

    # Если не нашли прямым совпадением, ищем по подстрокам 
    if not search_param:
        search_substrings = ["query", "search"]
        found_search_keys = []
        for key in data.keys():
            key_upper = key.upper()
            for substring in search_substrings:
                if substring.upper() in key_upper:
                    found_search_keys.append(key)
                    break
        
        if len(found_search_keys) == 1:
            search_param = found_search_keys[0]
        elif len(found_search_keys) >= 2:
            print(f"🟧 Найдено {len(found_search_keys)} ключей, содержащих подстроки для search_param: {found_search_keys}. Значение не присвоено.")
    
    if not pagination_param:
        pagination_substring = "page"
        found_pagination_keys = []
        for key in data.keys():
            if pagination_substring.upper() in key.upper():
                found_pagination_keys.append(key)
        
        if len(found_pagination_keys) == 1:
            pagination_param = found_pagination_keys[0]
        elif len(found_pagination_keys) >= 2:
            print(f"🟧 Найдено {len(found_pagination_keys)} ключей, содержащих подстроку '{pagination_substring}' для pagination_param: {found_pagination_keys}. Значение не присвоено.")

    # Если и по подстрокам не нашли, то используем ИИ

    def _build_ai_request(instruction: str) -> str:
        for AI_attempts in range(3): # YandexGPT не максимально хорошо понимает это, и иногда выдаёт длинный ответ
            AI_request = dedent(
                f"""
                В таком запросе: {current_url}
                Есть такие параметры: "{all_http_params}"
                {instruction}
                Обязательное правило:
                Не пиши никаких комментариев, пояснений, вариантов и текста вокруг, потому что я вставлю твой ответ сразу в код. 
                В результате выдай только один параметр.
                """
            ).strip()
            AI_answer = send_message_to_AI_agent(AI_request, no_hint=True)
            if(len(AI_answer) > 16):
                print("ИИ дал неверный ответ, пробуем ещё раз")
                continue
            return AI_answer.strip()
        return ""

    all_http_params = ", ".join(data.keys())

    if not search_param:
            print("Используем ИИ для поиска параметра, соответствующего запросу")
            search_param = _build_ai_request("Верни мне параметр, в котором задаётся запрос на поиск.")
    if not search_param:
        raise ErrorHandler("Не смогли подобрать параметр для поиска, в запросе")

    if not pagination_param:
        print("Используем ИИ для поиска параметра, соответствующего текущей странице")
        pagination_param = _build_ai_request("Верни мне параметр, в котором задаётся текущая страница (в данном случае страница = 2).")
    if not pagination_param:
        raise ErrorHandler("Не смогли подобрать параметр для пагинации")

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
        added_url_params += f'url.searchParams.set("{key}", "{value}")\n'

    set_item["search_param"] = search_param
    set_item["pagination_param"] = pagination_param
    set_item["added_url_params"] = added_url_params

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
    
    set_item["host"] = host
    set_item["path"] = path

    return set_item

    #TODO Потом переписать покрасивее тут всё





### Иногда нужно будет использовать set.page - 1
# Т.е. добавить проверку
# TODO Это можно оставить на доработку на будущее 


# region Шаблон
def generate_parsePage(set_item):
    # Эти значения вставляю в шаблон, если parsePage возвращает какие-то результаты
    # TODO значение не синхронизировано с global_code
    is_parse_page_mode_returned_results_bool = False
    elem_1_items = f"\nlet items: ResultItem[] = [];"
    elem_2_result_items = f"\nreturn items;"

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
        $elem_1_items_value
        let products = $$("$productSelector")
        if (products.length == 0) {
            this.logger.put(`По запросу $${set.query} ничего не найдено`)
            throw new NotFoundError()
        }
        products.slice(0, +this.conf.itemsCount).each((i, product) => {
            let link = $finalProductLink
            this.query.add({ ...set, query: link, type: "card", lvl: 1 })
        }) $elem_2_result_items_value
    }
    """)

    # Проверяем, есть ли в извлекаемой ссылке хост

    # убрать
    # result_once_search_elem = get_element_from_selector_universal(set_item["page_html"], set_item["product_selector"])
    # print("result_once_search_elem = " + result_once_search_elem)
    # if 

    finalProductLink_val = '$(product)?.attr("href")'
    if set_item.get("is_add_host") is True:
        finalProductLink_val = '`${HOST}${$(product)?.attr("href")}`'

    result = template_parseCard.substitute(
        hostPatch = set_item["path"],
        searchQuery = set_item["search_param"],
        paginationParams = set_item["pagination_param"],
        addedUrlParams = set_item["added_url_params"],
        
        result_pagination_block_value = set_item["result_pagination_block"],
        productSelector = set_item["product_selector"],
        #TODO Как-то проверить, что товар извлекается по $(product)?.attr("href")
        finalProductLink = finalProductLink_val,
        # Если в селкторе есть href в [] - то значит верно, также может быть src или текст

        elem_1_items_value = elem_1_items if is_parse_page_mode_returned_results_bool else "",
        elem_2_result_items_value = elem_2_result_items if is_parse_page_mode_returned_results_bool else ""
    ).strip()

    print(result)
    return result




# region main_generate_parsePage
def main_generate_parsePage():
    print(this_module_title)
    
    if (
        not data_input_table.get("timestamp") 
        or ((time.time() - data_input_table["timestamp"]) / 3600) > 6
    ):
        # print(f"Текущий timestamp = {int(time.time())}")
        # raise ErrorHandler("Данные для генерации parsePage старше 6 часов, и скорее всего не актуальны")
        print("🟧 timestamp нет в массиве, данные для parsePage могут быть неактуальными")

    #TODO Тут надо будет как-то обработать, что у нас не 1 пример, а 5

    # Извлекает url параметры поиска и пагинации из вхоящей ссылки
    set_item = generate_parsePage_search_requests(data_input_table)

    # Получает страницу
    set_item["page_html"] = get_html(set_item["link"]) 
    current_element = data_input_table["search_requests"][0]

    # Извлекаем product_selector
    processed_url_product = strip_host(current_element["links_items"][0])
    product_selector = get_css_selector_from_text_value_element(set_item["page_html"], processed_url_product, is_exact = False, is_multiply_sel_result = True)
    if not product_selector:
        raise ErrorHandler("Не был найден селектор для товара")
        # Это может быть, если сортировка товаров может меняться
        # TODO Как это можно обойти: 
            # Собрать все ссылки из страницы
            # И выделить те, которые указывают на товары
            # Можно сравнивать их с теми, что пришли по задаче для parseCard
            # И потом с использованием ИИ выделить их, и уже найти их селекторы
    
    print("\nproduct_selector = " + product_selector)

    # Проверяем, сколько товаров на этой странице
    tree = html_lx.fromstring(set_item["page_html"])
    search_elem = tree.cssselect(product_selector)
    len_of_products_on_this_page = len(search_elem)
    print(f"len_of_products_on_this_page = {len_of_products_on_this_page}")

    # Полчаем значения элементов, по этому селектороу
    match = re.search(r"\[(.*?)\]", product_selector)
    attr = match.group(1) if match else None  

    link_list = []
    for elem in search_elem:
        if attr:  # если селектор вида a[item]
            value = elem.get(attr)
        else:     # если просто тег — берём текст
            value = elem.text_content().strip()
        link_list.append(value)

    if len(link_list) < 6:
        raise ErrorHandler("Скорее всего селектор неверный, элементов < 6")

    # Добавляем хост ко всем ссылкам, если они извлекаются со страницы без него
    if link_list and set_item["host"] not in link_list[0]:
        link_list = [f'{set_item["host"]}{value}' for value in link_list]
        set_item["is_add_host"] = True
        
    # # # Печать уже из массива
    # # for value in link_list:
    # #     print(value)
    # print(link_list)

    # Рассчёт доли совпадающих ссылок на странице поиска, и во входном массиве
    # и проверка, что мы нашли верный селектор, и извлекаем верные ссылки
    links_items = current_element.get("links_items", [])
    if links_items:
        links_items_set = set(filter(None, links_items))
        link_list_set = set(filter(None, link_list))
        matched_links = links_items_set & link_list_set
        coverage_ratio = len(matched_links) / len(links_items_set) if links_items_set else 0
        print(f"Совпадение ссылок = {coverage_ratio:.2f} ({len(matched_links)}/{len(links_items_set)})")
        #TODO На сайте 1 работает плохо - там скорее всего ссылки динамически меняются
        # Надо подумать как проходить дальше этого
        if coverage_ratio == 0:
            raise ErrorHandler("Ни одной ссылки не совпало")
        if coverage_ratio < 0.6:
            raise ErrorHandler("Меньше 60% ссылок совпадают, считаем что на странице найдены неверные результаты")
    
    # Извлекаем селектор для пагинации

    #TODO Также может быть такая ситуация, что вообще нет параметров в поиске
    # это значит всё ищется запросами, и нужно будет смотреть их

    #TODO Сюда ещё надо добавить вариант, когда у нас указан оффсет, но нет пагинации
    # region _ex selector offset

    # Проверить на том сайте, №2 
    # Сейчас детектить, и кидать ошибку генерации parsePage
    # Надо будет дополнительно подумать о том, как это можно детектить, если у нас
    # есть только одна ссылка на вторую страницу

    # Можно вообще заменить извлечение параметров запроса - сделать через ИИ
    # Написать подробное задание, с примерами под каждый кейс
    # и что бы он выводил ответ в json формате

    """
        Если это ссылка на вторую страницу поиска товаров: https://santehnica-vodoley.ru/search/?find=%D0%92%D0%B0%D0%BD%D0%BD%D0%B0&curPos=24 То сгенерируй ссылку на третью страницу Не пиши никаких комментариев, пояснений, вариантов и текста вокруг. В результате выдай только одну ссылку
    """


    """
        Если у нас есть такая ссылка, на поиск товаров, на вторую страницу:

        https://santehnica-vodoley.ru/search/?find=%D0%92%D0%B0%D0%BD%D0%BD%D0%B0&curPos=24

        Ответь на вопрос, в этой ссылке используется параметр оффсета, при котором мы задаём не номер страницы, а смещение выдачи относительно первого товара? Обязательное правило: Не пиши никаких комментариев, пояснений, вариантов и текста вокруг. Выдай ответ "Нет", если здесь не используется параметр оффсета, и выдай в ответе этот параметр, если он есть - без каких либо пояснений
    """








    # region _ex selector pagin
    if(current_element["count_of_page_on_pagination"]) != "0": 
        print("Извлекаем селектор кол-ва страниц")
        #TODO Нужно будет чистить селектор от :nth-of-type(), если это будет нужно

        finding_element = current_element["count_of_page_on_pagination"]        
        pagination_selctor = get_css_selector_from_text_value_element(set_item["page_html"], finding_element, is_exact = False)

        print("pagination_selctor = " + pagination_selctor)

        checked_value = get_element_from_selector_universal(set_item["page_html"], pagination_selctor)
        print("Проверили, и нашли такой элемент по найденному селектору пагинации: " + checked_value)

        # И если мы далее будем использовать 
        # let totalPages = Math.max(...$("").get().map(item => +$(item).text().trim()).filter(Boolean))
        # То нужно проверить, работает ли это на этой странице
        # TODO Добавить проверку, что эта строчка сработает на этой странице
            # и что результат будет числом

        result_pagination_block = (
            f'let totalPages = Math.max(...$("{pagination_selctor}").get().map(item => +$(item).text().trim()).filter(Boolean))'
        )

    else: 
        # region _ex selector count
        print("Извлекаем селектор кол-ва товаров по запросу")
        
        finding_element = current_element["total_count_of_results"]
        
        pagination_selctor = get_css_selector_from_text_value_element(set_item["page_html"], finding_element, is_exact = False)
        if(pagination_selctor == ""):
            raise ErrorHandler("Не нашли селектора для извлечения количества найленных товаров")
            # Такая ошибка может возникнуть, если данные во входном массиве устарели, и на странице новое число
            #TODO Потенциальная ошибка
        print("pagination_selctor: " )
        print(pagination_selctor)

        # Проверяем, получаем ли мы по селектору именно нужный элемент
        checked_selector = get_element_from_selector_universal(set_item["page_html"], pagination_selctor)
        print("Проверили, и нашли такой элемент по найденному селектору: " + checked_selector)

        if(finding_element == checked_selector):
            print("Селектор корректен")
            extracting_pagination_1 = f'let totalItems = $("{pagination_selctor}")?.first()?.text()?.trim()'
        elif(checked_selector == ""):
            raise ErrorHandler("Ошибка, элемент числа товаров для пагинации не найден по селектору!")
        else:
            print("Нужное значение и извлекаемый элемент совпадают неточно, запускаю AI")
            js_code_extract_pagination = f'let totalItems = $("{pagination_selctor}")?.first()?.text()?.trim()'
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
            extracting_pagination_1 = send_message_to_AI_agent(request_AI)

            # Значение len_of_products_on_this_page проверяю и валидирую выше (если нет, то кидаю ошибку)
            extracting_pagination_2 = f'let totalPages = Math.ceil(+totalItems / {len_of_products_on_this_page})'
            
            result_pagination_block = extracting_pagination_1 + "\n" + extracting_pagination_2

        # На этом этапе мы получили первую строку, которая извлекает количество товаров на одной странице
        # Далее, нам нужно проверить, сколько элементов подгружается на странице
        # И для этого, нам нужно извлечь селектор, который указывает на товар
        # (а точнее на ссылку на товар)

    print("result_pagination_block = \n\n" + result_pagination_block) 

    set_item["result_pagination_block"] = result_pagination_block
    set_item["product_selector"] = product_selector

    # Генерирует итоговый шаблон parsePage
    result = generate_parsePage(set_item)
    return result



#######
# main_generate_parsePage()







###### Убрать все ErrorHandler
# Заменить их на print, и добавление в очередь сообщений об ошибках
# И добавление ошибок в итоговый код


### Предупреждение о несвежих данных также вывести в результирующий масив предупреждений


############# А также прописать возможно действительно один универсальный запрос,
# что бы ИИ извлекал весь кусок кода полностью
# т.е. прописать там ему правила, и скинуть примеры