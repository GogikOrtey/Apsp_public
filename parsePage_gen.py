# Подключение всех библиотек
from import_all_libraries import * 
from extracting_selector_from_html import * 
from gen_data_input_table import data_input_table # Входные данные
from addedFunc import *
from YandexGPT import *





this_module_title = """


--------------------------------------------------------------------------------------------------

                                         PARSE PAGE GEN

--------------------------------------------------------------------------------------------------

"""





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




def AI_generate_parsePage_search_requests(data_input_table):
    template_AI_request = Template("""
Тебе нужно написать код, который формирует URL адрес запроса на поиск товара. Мы используем такой синтаксис:

let url = new URL(`$${HOST}/search`)
url.searchParams.set("q", set.query)
url.searchParams.set("page", set.page)

Твоя задача: Выше в коде заданые переменные set.query - это текст запроса на поиск, и set.page - это текущая страница поиска, она начинается с 1. Тебе нужно написать и вернуть только необходимый фрагмент кода на JS, в котором будет формироваться URL с использованием этих параметров. Чаще всего параметры поиска и текущей страницы задаются в searchParams, но иногда они задаются напрямую в строке URL, в таком случае нужно будет использовать синтаксис с `$${}`. Также, в исходном URL могут быть заданы дополнительные параметры, которые не влияют на запрос и текущую страницу, все эти параметры нужно будет сохранить.

Пример 1:
Строка на поиск у сайта, на 2ю страницу поиска: 
https://galen.bg/catalogsearch/result/index/?p=2&q=мл

Фрагмент с формированием URL:
let url = new URL(`$${HOST}/catalogsearch/result/index/`)
url.searchParams.set("q", set.query)
url.searchParams.set("p", set.page)

Пример 2:
Строка на поиск у сайта, на 2ю страницу поиска: 
https://stroytorg812.ru/content/search/?s=&q=Ванна&PAGEN_1=2

Фрагмент с формированием URL:
let url = new URL(`$${HOST}/content/search/`)
url.searchParams.set("s", "")
url.searchParams.set("q", set.query)
url.searchParams.set("PAGEN_1", set.page)


Пример 3:
Строка на поиск у сайта, на 2ю страницу поиска: 
https://gidro-top.ru/search/Ванна/?page=2

Фрагмент с формированием URL:
let url = new URL(`$${HOST}/search/$${set.query}/`)
url.searchParams.set('/?page', set.page);

-----

Текущее задание:
Строка на поиск у сайта, на 2ю страницу поиска: $url_search_2_page

Значение переменной HOST = $host_value

Обязательное правило: Никаких комментариев, пояснений, вариантов и текста вокруг в результате выдай только один финальный фрагмент кода - Фрагмент с формированием URL.
    """)

    AI_request = template_AI_request.substitute(
        host_value = data_input_table["host"],
        url_search_2_page = data_input_table["search_requests"][0]["url_search_query_page_2"]
    ).strip()

    AI_answer = send_message_to_AI_agent(AI_request, no_hint=True).strip()

    set_item = {}
    set_item["create_url_block"] = ("\n".join(f"\t\t" + line for line in AI_answer.splitlines())).lstrip()
    return set_item

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
        $create_url_block

        const data = await this.makeRequest(url.href)
        const $$ = cheerio.load(data)

        if (set.page === 1) {
            $result_pagination_block_value $error_msg_2
            this.debugger.put(`totalPages = $${totalPages}`)
            for (let page = 2; page <= Math.min(totalPages, +this.conf.pagesCount); page++) {
                this.query.add({ ...set, query: set.query, type: "page", page: page, lvl: 1 });
            }
        }
        $elem_1_items_value
        let products = $$("$productSelector") $error_msg_1
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
    finalProductLink_val = '$(product)?.attr("href")'
    if set_item.get("is_add_host") is True:
        finalProductLink_val = '`${HOST}${$(product)?.attr("href")}`'

    error_message = "// [Ошибка генерации APSP]: Не удалось подобрать значения для поля"

    result = template_parseCard.substitute(
        result_pagination_block_value = set_item.get("result_pagination_block") or "let totalPages = 0",
        productSelector = set_item.get("product_selector") or "",
        #TODO Как-то проверить, что товар извлекается по $(product)?.attr("href")
        finalProductLink = finalProductLink_val,
        # Если в селкторе есть href в [] - то значит верно, также может быть src или текст
        create_url_block = set_item.get("create_url_block") or "",

        elem_1_items_value = elem_1_items if is_parse_page_mode_returned_results_bool else "",
        elem_2_result_items_value = elem_2_result_items if is_parse_page_mode_returned_results_bool else "",

        error_msg_1 = error_message if not set_item.get("product_selector") else "",
        error_msg_2 = error_message if not set_item.get("result_pagination_block") else ""
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
        message_global.append({"2": f"timestamp нет в массиве, данные для parsePage могут быть неактуальными"})

    #TODO Тут надо будет как-то обработать, что у нас не 1 пример, а 5

    # Извлекает url параметры поиска и пагинации из вхоящей ссылки
    # set_item = generate_parsePage_search_requests(data_input_table)

    ################################ вернуть
    # set_item = AI_generate_parsePage_search_requests(data_input_table)
    set_item = {
        "create_url_block": "временно отключил"
    }

    set_item["link"] = data_input_table["search_requests"][0]["url_search_query_page_2"]
    set_item["host"] = data_input_table["host"]

    # Получает страницу
    set_item["page_html"] = get_html(set_item["link"]) 
    current_element = data_input_table["search_requests"][0]

    # TODO Это изменить - на нормальный перебор и суммарайзинг селекторов из всех ссылок что у нас есть
    
    
    # for use_id_link_elem in range(0, len(current_element["links_items"])):
    #     # Извлекаем product_selector
    #     processed_url_product = strip_host(current_element["links_items"][use_id_link_elem])
    #     print(f"processed_url_product = {processed_url_product}")
    #     product_selector = get_css_selector_from_text_value_element(set_item["page_html"], processed_url_product, is_exact = False, is_multiply_sel_result = True)
    #     product_selector = clean_selector_from_double_hyphen(product_selector)
        
    #     if not product_selector:
    #         raise ErrorHandler("Не был найден селектор для товара")
    #         # Селектор устарел, обновите данные в gen_data_input_table

    #         # Это может быть, если сортировка товаров может меняться
    #         # TODO Как это можно обойти: 
    #             # Собрать все ссылки из страницы
    #             # И выделить те, которые указывают на товары
    #             # Можно сравнивать их с теми, что пришли по задаче для parseCard
    #             # И потом с использованием ИИ выделить их, и уже найти их селекторы

    #     print("\nproduct_selector = " + product_selector)

    #     # Проверяем, сколько товаров на этой странице
    #     tree = html_lx.fromstring(set_item["page_html"])
    #     search_elem = tree.cssselect(product_selector)
    #     len_of_products_on_this_page = len(search_elem)
    #     print(f"len_of_products_on_this_page = {len_of_products_on_this_page}")

    #     # Полчаем значения элементов, по этому селектороу
    #     match = re.search(r"\[(.*?)\]", product_selector)
    #     attr = match.group(1) if match else None  

    #     link_list = []
    #     for elem in search_elem:
    #         if attr:  # если селектор вида a[item]
    #             value = elem.get(attr)
    #         else:     # если просто тег — берём текст
    #             value = elem.text_content().strip()
    #         link_list.append(value)

    #     if len(link_list) < 6:
    #         # raise ErrorHandler("Скорее всего селектор неверный, элементов < 6")
    #         print("🟡 Скорее всего селектор неверный, элементов < 6")
    #         print("Пробуем другие ссылки")
    #     break





    # Извлекаем product_selector
    processed_url_product = strip_host(current_element["links_items"][0])
    print(f"processed_url_product = {processed_url_product}")
    original_product_selector = get_css_selector_from_text_value_element(set_item["page_html"], processed_url_product, is_exact=False, is_multiply_sel_result=True)
    original_product_selector = clean_selector_from_double_hyphen(original_product_selector)

    if not original_product_selector:
        raise ErrorHandler("Не был найден селектор для товара")

    tree = html_lx.fromstring(set_item["page_html"])
    product_selector = None

    # Функция для разделения селектора на части по комбинаторам
    def split_selector_by_combinators(selector):
        # Регулярное выражение для поиска CSS комбинаторов
        # Поддерживаем: пробел, >, +, ~
        pattern = r'(\s+|\s*>\s*|\s*\+\s*|\s*~\s*)'
        parts = re.split(pattern, selector)
        
        # Фильтруем пустые строки и объединяем части с их комбинаторами
        result = []
        current_part = ""
        
        for i, part in enumerate(parts):
            if not part.strip():
                continue
                
            # Если это комбинатор
            if part.strip() in ['>', '+', '~'] or part.isspace():
                if current_part:
                    result.append(current_part.strip())
                    current_part = ""
                result.append(part.strip())
            else:
                if current_part and not any(result[-1] in ['>', '+', '~'] for item in result[-1:]):
                    current_part += " " + part
                else:
                    current_part = part
        
        if current_part:
            result.append(current_part.strip())
        
        # Группируем в пары: элемент + комбинатор (если есть)
        grouped = []
        i = 0
        while i < len(result):
            if i + 1 < len(result) and result[i+1] in ['>', '+', '~']:
                grouped.append(f"{result[i]}{result[i+1]}")
                i += 2
            else:
                grouped.append(result[i])
                i += 1
        
        return grouped

    # Функция для сборки селектора из частей
    def build_selector_from_parts(parts):
        selector = ""
        for i, part in enumerate(parts):
            # Проверяем, содержит ли часть комбинатор в конце
            if part.endswith('>'):
                selector += part
            elif part.endswith('+'):
                selector += part
            elif part.endswith('~'):
                selector += part
            elif i < len(parts) - 1:
                # Следующая часть начинается с комбинатора?
                next_part = parts[i + 1]
                if next_part.startswith(('>', '+', '~')):
                    selector += part
                else:
                    selector += part + " "
            else:
                selector += part
        
        return selector.strip()

    # Разбиваем селектор на части
    selector_parts = split_selector_by_combinators(original_product_selector)
    print(f"Исходный селектор: {original_product_selector}")
    print(f"Части селектора: {selector_parts}")
    print(f"Количество частей: {len(selector_parts)}")

    # Итерируемся по количеству элементов в селекторе
    for i in range(len(selector_parts)):
        # Создаем текущий селектор, начиная с i-й части
        current_parts = selector_parts[i:]
        current_selector = build_selector_from_parts(current_parts)
        print(f"\nПроверяем селектор: {current_selector}")
        
        # Проверяем количество элементов по текущему селектору
        search_elem = tree.cssselect(current_selector)
        len_of_products = len(search_elem)
        print(f"Найдено элементов: {len_of_products}")

        if len_of_products < 6 and len(current_parts) != 1:
            continue
        
        # Проверяем условия
        if len_of_products <= 100:
            # Получаем значения элементов для проверки
            match = re.search(r"\[(.*?)\]", current_selector)
            attr = match.group(1) if match else None
            
            link_list = []
            for elem in search_elem:
                if attr:
                    value = elem.get(attr)
                else:
                    value = elem.text_content().strip()
                link_list.append(value)
            
            # Проверяем, не остался ли один элемент в селекторе
            if len(current_parts) == 1:
                if len_of_products < 6: ######################################################## <
                    raise ErrorHandler(f"Селектор содержит только одну часть и элементов < 6: найдено {len_of_products} элементов")
                else:
                    product_selector = current_selector
                    print(f"✅ Найден подходящий селектор: {product_selector}")
                    break
            else:
                product_selector = current_selector
                print(f"✅ Найден подходящий селектор: {product_selector}")
                break
        else:
            print(f"Слишком много элементов ({len_of_products}), удаляем левую часть")

    # Если не нашли подходящий селектор
    if product_selector is None:
        # Проверяем последний возможный селектор (последнюю часть)
        last_selector_parts = [selector_parts[-1]]
        last_selector = build_selector_from_parts(last_selector_parts)
        search_elem = tree.cssselect(last_selector)
        len_of_products = len(search_elem)
        
        if len_of_products < 6:
            raise ErrorHandler(f"Даже с одной частью слишком мало элементов: найдено {len_of_products} элементов")
        else:
            raise ErrorHandler(f"Не удалось найти селектор с <=100 элементами. Последний вариант: {len_of_products} элементов")

    print(f"\nИтоговый product_selector = {product_selector}")
    print(f"Количество элементов по итоговому селектору: {len(tree.cssselect(product_selector))}")

    # ################# Вот здесь ошибкка, неверное получение по селектору
    # # Проверяем, сколько товаров на этой странице по итоговому селектору
    # search_elem = tree.cssselect(product_selector)
    # len_of_products_on_this_page = len(search_elem)
    # print(f"len_of_products_on_this_page = {len_of_products_on_this_page}")

    # # Получаем значения элементов по этому селектору
    # match = re.search(r"\[(.*?)\]", product_selector)
    # attr = match.group(1) if match else None  

    # link_list = []
    # for elem in search_elem:
    #     if attr:  # если селектор вида a[item]
    #         value = elem.get(attr)
    #     else:     # если просто тег — берём текст
    #         value = elem.text_content().strip()
    #     link_list.append(value)

    link_list = get_element_from_selector_universal(set_item["page_html"], product_selector, return_all = True)

    print(f"Ссылок по селектору: {len(link_list)}")


    # Добавляем хост ко всем ссылкам, если они извлекаются со страницы без него
    if link_list and link_list[0] and set_item["host"] not in link_list[0]:
        link_list = [f'{set_item["host"]}{value}' for value in link_list]
        set_item["is_add_host"] = True

            
    # # # Печать уже из массива
    # # for value in link_list:
    # #     print(value)
    # print(link_list)

    # # Рассчёт доли совпадающих ссылок на странице поиска, и во входном массиве
    # # и проверка, что мы нашли верный селектор, и извлекаем верные ссылки
    # links_items = current_element.get("links_items", [])
    # if links_items:
    #     links_items_set = set(filter(None, links_items))
    #     link_list_set = set(filter(None, link_list))
    #     matched_links = links_items_set & link_list_set
    #     coverage_ratio = len(matched_links) / len(links_items_set) if links_items_set else 0
    #     print(f"Совпадение ссылок = {coverage_ratio:.2f} ({len(matched_links)}/{len(links_items_set)})")
    #     #TODO На сайте 1 работает плохо - там скорее всего ссылки динамически меняются
    #     # Надо подумать как проходить дальше этого
    #     if coverage_ratio == 0:
    #         # raise ErrorHandler("Ни одной ссылки не совпало")
    #         message_global.append({"1": f"Ни одной ссылки не совпало"})
    #         result = generate_parsePage(set_item)
    #         return result
    #     if coverage_ratio < 0.6:
    #         # raise ErrorHandler("Меньше 60% ссылок совпадают, считаем что на странице найдены неверные результаты")
    #         message_global.append({"1": f"Меньше 60% ссылок совпадают, считаем что на странице найдены неверные результаты"})
    #         result = generate_parsePage(set_item)
    #         return result


    # Рассчёт доли совпадающих ссылок на странице поиска, и во входном массиве
    # и проверка, что мы нашли верный селектор, и извлекаем верные ссылки
    links_items = current_element.get("links_items", [])
    if links_items:

        print("links_items = ")
        print(links_items)
        print("link_list = ")
        print(link_list)

        # Фильтруем пустые значения
        links_items_filtered = list(filter(None, links_items))
        link_list_filtered = list(filter(None, link_list))

        print("links_items_filtered = ")
        print(links_items_filtered)
        print("link_list_filtered = ")
        print(link_list_filtered)
        
        # Считаем, сколько ссылок из links_items найдено на странице
        found_count = 0
        
        for link_item in links_items_filtered:
            # Для каждой ссылки из links_items проверяем, есть ли она на странице
            found = False
            
            for link_page in link_list_filtered:
                # Сравниваем две строки с помощью compute_match_score
                match_score = compute_match_score(link_item, link_page)
                
                # Если совпадение больше 70%, считаем что ссылка найдена
                if match_score > 0.7:
                    found = True
                    break  # Прерываем внутренний цикл, если нашли совпадение
            
            if found:
                found_count += 1
        
        # Вычисляем долю найденных ссылок
        coverage_ratio = found_count / len(links_items_filtered) if links_items_filtered else 0
        
        print(f"Совпадение ссылок = {coverage_ratio:.2f} ({found_count}/{len(links_items_filtered)})")
        
        # Проверяем результат
        if coverage_ratio == 0:
            message_global.append({"1": f"Ни одной ссылки не совпало"})
            result = generate_parsePage(set_item)
            return result
        
        if coverage_ratio < 0.6:
            message_global.append({"1": f"Меньше 60% ссылок совпадают, считаем что на странице найдены неверные результаты"})
            result = generate_parsePage(set_item)
            return result
    
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


    # Ещё возможно что у нас указано кол-во найденных товаров, но нет пагинации
    # и нужно будет посчитать количество элементов на этой странице, и разделить на общее





    # region _ex selector pagin
    if(current_element["count_of_page_on_pagination"]) != "0": 
        print("Извлекаем селектор кол-ва страниц")
        #TODO Нужно будет чистить селектор от :nth-of-type(), если это будет нужно
        #TODO Да, следует удалять такие части li:nth-of-type(5)[data-value]
        # что бы селектор был более точным, либо задавать их от конца а не от начала, 
        # если он извлекает параметр в [] а не текст

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
            # raise ErrorHandler("Не нашли селектора для извлечения количества найденных товаров")
            message_global.append({"1": f"Не нашли селектора для извлечения количества найденных товаров"})
            result = generate_parsePage(set_item)
            return result
            # Такая ошибка может возникнуть, если данные во входном массиве устарели, и на странице новое число
            #TODO Потенциальная ошибка
        print("pagination_selctor: " )
        print(pagination_selctor)

        # Проверяем, получаем ли мы по селектору именно нужный элемент
        checked_selector = get_element_from_selector_universal(set_item["page_html"], pagination_selctor)
        print("Проверили, и нашли такой элемент по найденному селектору: " + checked_selector)

        if(finding_element == checked_selector):
            print("Селектор корректен")
            extracting_pagination_1 = f'\t\t\tlet totalItems = $("{pagination_selctor}")?.first()?.text()?.trim()'
        elif(checked_selector == ""):
            # raise ErrorHandler("Ошибка, элемент числа товаров для пагинации не найден по селектору!")
            message_global.append({"1": f"Ошибка, элемент числа товаров для пагинации не найден по селектору!"})
            result = generate_parsePage(set_item)
            return result
        else:
            print("Нужное значение и извлекаемый элемент совпадают неточно, запускаю AI")
            js_code_extract_pagination = f'\t\t\tlet totalItems = $("{pagination_selctor}")?.first()?.text()?.trim()'
            print("js_code_extract_pagination = " + js_code_extract_pagination)
            
            request_AI = dedent(
                f"""
                Есть такой код на JS: 
                {js_code_extract_pagination.strip()}
                Однако он извлекает "{checked_selector}"
                А должен извлекать: "{finding_element}"
                Измени исходный код, что бы он делал это.
                """
            ).strip()
            extracting_pagination_1 = send_message_to_AI_agent(request_AI).strip()

            # Значение len_of_products_on_this_page проверяю и валидирую выше (если нет, то кидаю ошибку)
            extracting_pagination_2 = f'\t\t\tlet totalPages = Math.ceil(+totalItems / {len_of_products_on_this_page})'
            
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
