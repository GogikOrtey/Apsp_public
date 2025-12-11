# Подключение всех библиотек
from import_all_libraries import * 

# Вынесенные отдельно функции
from addedFunc import *
from gen_data_input_table import data_input_table # Входные данные
from extracting_selector_from_html import * 
from YandexGPT import send_message_to_AI_agent
from saving_cache import * 

isPrint = False





this_module_title = """


--------------------------------------------------------------------------------------------------

                                         PARSE CARD GEN

--------------------------------------------------------------------------------------------------

"""




# region Создаю parseCard

def format_js(code: str) -> str:
    opts = jsbeautifier.default_options()
    opts.indent_size = 2
    opts.wrap_line_length = 120
    return jsbeautifier.beautify(code, opts)

# Собирает финальный код для вставки в шаблон
def selector_checker_and_parseCard_gen(result_selectors, data_input_table):
    print("Проверяем селекторы, и генерируем parseCard")
    #print_json(result_selectors)  

    # print("data_input_table = ")
    # print(data_input_table)
    # print("")

    # Подготовка множества триггеров InStock (строки)
    all_inStock_selectors = {elem.get("InStock_trigger") for elem in data_input_table["links"]["simple"] if elem.get("InStock_trigger")}
    all_inStock_selectors = {s if isinstance(s, str) else ",".join(s) for s in all_inStock_selectors}
    count_of_unical_text_selectors = len(all_inStock_selectors)

    # Вспомог: объединяем массив селекторов в одну строку для $("sel1, sel2")
    def join_selectors_array(sel_array):
        # sel_array ожидается список строк
        if not sel_array:
            return ""
        # убираем лишние пробелы
        sel_array = [s.strip() for s in sel_array if s and s.strip()]
        if not sel_array:
            return ""
        if len(sel_array) == 1:
            return sel_array[0]
        # объединяем через запятую — это корректно для cheerio/jQuery
        return ", ".join(sel_array)

    # # Вспомог: извлекает атрибут из квадратных скобок в селекторе и удаляет его
    # def extract_and_remove_attr_from_selector(sel_array):
    #     """
    #     Ищет атрибут в квадратных скобках в селекторе.
    #     Например: '.img > a.fancybox[href]' -> ('.img > a.fancybox', 'href')
    #     Возвращает: (очищенный массив селекторов, имя атрибута или None)
    #     """
    #     cleaned_array = []
    #     found_attr = None
        
    #     for sel in sel_array:
    #         # Ищем атрибут в квадратных скобках
    #         # Паттерн: [attr] или [attr="value"] или [attr='value']
    #         pattern = r'\[([a-zA-Z][a-zA-Z0-9_-]*)(?:=["\'].*?["\'])?\]'
    #         match = re.search(pattern, sel)
            
    #         if match:
    #             # Найден атрибут, извлекаем его имя
    #             attr_name = match.group(1)
    #             # Удаляем атрибут из селектора
    #             cleaned_sel = re.sub(pattern, '', sel)
    #             cleaned_array.append(cleaned_sel)
    #             # Сохраняем первый найденный атрибут (если их несколько, берем первый)
    #             if found_attr is None:
    #                 found_attr = attr_name
    #         else:
    #             cleaned_array.append(sel)
        
    #     return cleaned_array, found_attr

    def extract_and_remove_attr_from_selector(sel_array):
        """
        Ищет атрибут в квадратных скобках в селекторе.
        Если атрибутов несколько, удаляет только последний.
        Например: '.img > a.fancybox[href][target]' -> ('.img > a.fancybox[href]', 'target')
        Возвращает: (очищенный массив селекторов, имя атрибута или None)
        """
        cleaned_array = []
        found_attr = None
        
        for sel in sel_array:
            # Ищем ВСЕ атрибуты в квадратных скобках в текущем селекторе
            # Используем finditer для получения всех вхождений с позициями
            all_attrs = list(re.finditer(r'(\[[^\]]+\])', sel))
            
            if all_attrs:
                # Берем последний найденный атрибут
                last_attr = all_attrs[-1]
                
                # Извлекаем содержимое атрибута (без скобок)
                attr_content = last_attr.group(1)[1:-1]  # Убираем квадратные скобки
                
                # Проверяем, содержит ли атрибут значение (с оператором =)
                # Если содержит =, то это условие поиска, а не атрибут для извлечения
                # Для извлечения нужен атрибут без оператора (просто имя)
                if '=' not in attr_content:
                    # Это атрибут для извлечения (просто имя атрибута)
                    attr_name = attr_content.strip()
                    # Удаляем только этот (последний) атрибут из селектора
                    start = last_attr.start()
                    end = last_attr.end()
                    cleaned_sel = sel[:start] + sel[end:]
                    cleaned_array.append(cleaned_sel)
                    found_attr = attr_name
                else:
                    # Это условие поиска (с оператором =), оставляем как есть
                    cleaned_array.append(sel)
            else:
                # Атрибутов нет в этом селекторе
                cleaned_array.append(sel)
        
        return cleaned_array, found_attr

    # region Поле stock
    # Генератор куска для триггера наличия 
    def using_InStock_triggers_value(result_selectors_local, use_OutOfStock=False):
        key_stock = "InStock_trigger" if not use_OutOfStock else "OutOfStock_trigger"
        true_value = '"InStock"' if not use_OutOfStock else '"OutOfStock"'
        false_value = '"OutOfStock"' if not use_OutOfStock else '"InStock"'

        sel_array = result_selectors_local.get(key_stock, [])
        sel_string = join_selectors_array(sel_array)
        if not sel_string:
            return f'\t\tconst stock = "InStock"\n'

        # all_inStock_selectors_js — javascript literal: либо "string", либо ["a","b"]
        if count_of_unical_text_selectors == 1:
            all_js = f'"{next(iter(all_inStock_selectors))}"'
        else:
            all_js = "[" + ", ".join(f'"{x}"' for x in all_inStock_selectors) + "]"

        if count_of_unical_text_selectors == 1:
            # условие: $("...").text()?.includes("needle")
            result_stock_selector = (
                f'\t\tconst stock = $("{sel_string}").text()?.includes({all_js}) ? {true_value} : {false_value}'
            )
        else:
            # несколько триггеров: .some(s => $("...").text()?.includes(s))
            result_stock_selector = (
                f'\t\tconst stock = {all_js}.some(s => $("{sel_string}").text()?.includes(s)) ? {true_value} : {false_value}'
            )

        return result_stock_selector

    # Обработка логики наличия
    if "InStock_trigger" not in result_selectors and "OutOfStock_trigger" not in result_selectors:
        print("Нет триггеров наличия, считаем что все товары в наличии")
        result_stock_selector = f'\t\tconst stock = "InStock"\n'
    elif "InStock_trigger" in result_selectors and "OutOfStock_trigger" in result_selectors:
        print("Оба триггера есть")
        # если указаны одинаковые массивы/строки — используем InStock как приоритет
        if result_selectors["InStock_trigger"] == result_selectors["OutOfStock_trigger"]:
            print("Они одинаковые, используем InStock")
            result_stock_selector = using_InStock_triggers_value(result_selectors)
        else:
            # логика: если есть оба и разные — используем InStock триггер как в оригинале (можно расширить)
            result_stock_selector = using_InStock_triggers_value(result_selectors)
    elif "InStock_trigger" in result_selectors and "OutOfStock_trigger" not in result_selectors:
        print("Есть только триггер InStock, используем его")
        result_stock_selector = using_InStock_triggers_value(result_selectors)
    elif "InStock_trigger" not in result_selectors and "OutOfStock_trigger" in result_selectors:
        print("Есть только триггер OutOfStock, используем его")
        result_stock_selector = using_InStock_triggers_value(result_selectors, use_OutOfStock=True)

    # region Остальные поля
    # Начинаем собирать varFromSelector для всех остальных полей
    lines = []
    # добавляем строку stock
    lines.append(result_stock_selector.rstrip("\n"))

    result_logger_fields = []    

    # Перебираем ключи
    for key, sel_array in result_selectors.items():
        if key in ("InStock_trigger", "OutOfStock_trigger"):
            # Пропускаем триггеры для поля stock, их уже обработали
            continue
        if not isinstance(sel_array, (list, tuple)):
            sel_array = [sel_array] if sel_array else []

        current_finded_selector_value_on_logger = ""

        # Переменные параметров для доп. настройки финальной строки JS кода
        max_count_element_of_selectors = 0 # Сколько максимально результатов было найдено по этому селектору на каждой странице
        is_add_host = False # Нужно ли добавить хост перед результатом поля?
        is_error_generation_selector = False # Если произошла ошибка при генерации строки кода
        elem_selector_first = "" # Нужно ли добавить ?.first() после извлечения результата селектора?
        is_use_comma_on_formatPrice = ""
        count_page = 0
        
        is_clarify_code_selector = False # Потребуется ли помощь ИИ для этой строки кода?
        ccs_result_value = "" # Первое значение, которое мы получили из селектора
        ccs_necessary_value = "" # Первое значение, которое мы должны были получить

        print(f"Обрабатываем поле {key}")

        # Проверяем селектор на всех ссылках из кеша
        for link_item in data_input_table["links"]["simple"]:
            count_page += 1
            link = link_item.get("link")
            if not link:
                continue
            
            # Получаем HTML из кеша
            html = get_html_from_cache(link, print_msg = False)
            for current_selector_query in sel_array:
                print("")
                print(f"Проверяем селектор {current_selector_query} на странице №{count_page}")
                result_selector = get_element_from_selector_universal(html, current_selector_query, is_ret_len=True)
                # Если элемент по селектору не был найден на одной или нескольких страницах, то это ничего страшного
                max_count_element_of_selectors = (
                    result_selector["length_elem"] if result_selector["length_elem"] > max_count_element_of_selectors 
                    else max_count_element_of_selectors
                )

                selector_result_data = result_selector["result"]
                original_field_value = link_item.get(key)

                # Проверяем соответствие, только если по селектору что-то было найдено на странице
                if selector_result_data:
                    host = data_input_table["host"]
                    if key == "imageLink":
                        if host not in selector_result_data:
                            print(f"    В элементе {selector_result_data} отсутствует хост. Добавляем:")
                            selector_result_data = host + selector_result_data
                            is_add_host = True

                    # print(f"💠{selector_result_data}💠") # Что селектор вернул
                    # print(f"🔶{original_field_value}🔶") # Что лежит во входном массиве

                    print(f"    {selector_result_data}") # Что селектор вернул
                    print(f"    {original_field_value}") # Что лежит во входном массиве
                    print("")

                    # Отдельно обрабатываю денежные поля
                    if key in ["price", "oldprice"]:
                        print(f"    💲 Обрабатываем поле {key}")
                        current_finded_selector_value_on_logger = "💲 "

                        p1 = format_price(selector_result_data)
                        p2 = format_price(selector_result_data, ",")

                        if p1 != p2:
                            print(f"    p1 = {p1}")
                            print(f"    p2 = {p2}")
                        
                        # TODO Простейшая проверка - попробовать пройтись parseInt

                        if p1.endswith("."):
                            is_use_comma_on_formatPrice = '","'
                            # Очень простая проверка, нужно будент убедиться что она покрывает все случаи
                            print('    Разделитель - запятая')
                        else:
                            print('    Разделитель - точка')
                        
                        # TODO Потом здесь подробнее оттестировать
                        continue
                    
                    score_match = compute_match_score_2(selector_result_data, original_field_value)
                    if selector_result_data == original_field_value:
                        print(f"    ✅ Полное совпадение селектора и оригинального значения поля {key}")
                        current_finded_selector_value_on_logger = "🟩"
                    elif (
                            selector_result_data in original_field_value 
                            or original_field_value in selector_result_data 
                            or score_match >= 0.8
                    ):
                        print("    🟨 Частичное совпадение")
                        current_finded_selector_value_on_logger = "🟨"

                        # Сохраняю для сообщения к ИИ на исправление строки кода,
                        # только первое значение
                        # TODO Потом возможно сохранять несколько, или хотя бы 2 первых
                        is_clarify_code_selector = True
                        if ccs_result_value == "":
                            ccs_result_value = selector_result_data
                            ccs_necessary_value = original_field_value
                    else:
                        print(f"    🟧 Нет совпадений. score_match = {score_match}")
                        current_finded_selector_value_on_logger = "🟧"
                        # В целом, по алгоритму такого не должно произойти
                        is_error_generation_selector = True
                else:
                    print(f"    ⬜ Нет результата у селектора {selector_result_data} на странице {count_page} для поля {key}")

        added_inf_from_logger = ""

        print("")
        print(f"max_count_element_of_selectors = 🟡 {max_count_element_of_selectors}")
        print(f"_____")
        print("")

        if len(sel_array) > 1 or max_count_element_of_selectors > 1:
            print(f"Нашли больше одного селектора для поля {key}")
            elem_selector_first = "?.first()"
            added_inf_from_logger += " 🟡 > 1"

        # Извлекаем атрибут из квадратных скобок и удаляем его из селектора
        sel_array, attr = extract_and_remove_attr_from_selector(sel_array)
        
        sel_string = join_selectors_array(sel_array)
        if not sel_string or max_count_element_of_selectors == 0 or is_error_generation_selector:
            # если селектор пуст — создаём пустую переменную
            result_code_line = f'\t\tconst {key} = "" // [Ошибка генерации APSP]: Не удалось подобрать селектор для поля'
            lines.append(result_code_line)
            message_global.append({"1": f"Ошибка генерации строки кода извлечения значения по селектору, для поля {key}: {result_code_line.split('//')[0]}"})
            current_finded_selector_value_on_logger = "🟧"
            continue

        add_formatPrice = ""
        if key in ["price", "oldprice"]:
            add_formatPrice = f".formatPrice({is_use_comma_on_formatPrice})"

        sel_string = sel_string.replace('"', "'") # Заменяем кавычки, если попались в селекторе

        selector_result_code = ""
        if attr: # Пример:           $("h1.name")     ?.first()            ?.attr("href")?.trim()
            attr = attr.replace('"', "'")
            selector_result_code = f'$("{sel_string}"){elem_selector_first}?.attr("{attr}")?.trim(){add_formatPrice}'
        else:    # Пример:           $("h1.name")     ?.first()            .text()?.trim()
            selector_result_code = f'$("{sel_string}"){elem_selector_first}.text()?.trim(){add_formatPrice}'

        # line_result_code = ""
        # if is_add_host: # По большей части, используется для поля imageLink
        #                 # тут мы хост приделываем спереди, если извлекли ссылку
        #     line_result_code = f'\t\tconst {key} = {selector_result_code} ? HOST + {selector_result_code} : ""'
        # else:
        #     line_result_code = f'\t\tconst {key} = {selector_result_code}'

        line_result_code = ""
        if is_add_host: # По большей части, используется для поля imageLink
                        # тут мы хост приделываем спереди, если извлекли ссылку
            line_result_code = f'\t\tconst {key} = {selector_result_code} ? HOST + {selector_result_code} : ""'
        else:
            line_result_code = f'\t\tconst {key} = {selector_result_code}'


        """ #############
        Потом переделать логику imageLink под это:
        
        let imageLink = $(".detail-gallery-big__link").attr('href');
        imageLink = imageLink ? HOST + imageLink : "";

        Также интересный шаблон для imageLink

        const src = $('.detail-gallery-big__picture').attr('src') ?? '';
        const imageLink = src.startsWith('http') ? src : `${HOST}${src}`;        

        """

        if is_clarify_code_selector:
            # Прошу ИИ дополнить строку кода
            print(f"🧢 Отправляю запрос к ИИ на исправление строки кода для поля {key}")
            added_inf_from_logger += " 🧢 use ИИ"
            add_info = ""
            if key == "imageLink":
                add_info += f"Переменная HOST = {data_input_table['host']}"
                
            request_AI = dedent(
                f"""
                Есть такой код на JS: 
                {line_result_code}
                Однако он извлекает "{ccs_result_value}"
                А должен извлекать: "{ccs_necessary_value}"
                {add_info}
                Измени исходный код, что бы он делал это.
                """
            ).strip()
            # Можно добавить:
            # И во втором примере
            # ...
            # хотя примеров может быть 1, на 3 входящие ссылки
            ai_result = send_message_to_AI_agent(request_AI)
            # Добавляем табы к каждой строке результата (на случай многострочного кода)
            ai_result_lines = ai_result.split('\n')
            line_result_code = '\n'.join(f"\t\t{line}" if line.strip() else line for line in ai_result_lines)

        # Добавляем строку кода в финальный массив, который вставляем в шаблон
        lines.append(line_result_code)

        result_logger_fields.append(f"{current_finded_selector_value_on_logger}: {key} {added_inf_from_logger}")





        """

            * Просмотреть на 20-30 примерах написанных парсеров

            * Логика для поля stock выписана, и была проверена, но давно
                * Стоит проверить её ещё раз
                    * Но проверять уже на примерах

            * Добавить сообщения об ошибках
                * В общкю область, в виде словаря формата:
                0 - предупреждение
                1 - ошибка
                {"1": "Ошибка генерации строки кода извлечения значения по селектору, для поля {поле}: {
                вся строка, до комментария}"}
                они будут выводиться в конце генерации

        """

    
    print("Статистика нахождения селекторов:")
    for elem in result_logger_fields:
        print(elem)
    print("")

    # region Генерируем шаблон
    lines.append(f"\t\tconst link = set.query")

    # Собираем финальную строку varFromSelector   
    value_field = "\n".join(lines) + "\n"

    # В конце убираем завершающие переносы
    value_field = value_field.rstrip("\n")

    # print("value_field = ")
    # print(value_field)

    ## Это будет приходить из global_code
    # order_string = "name, stock, link, price, oldprice, article, brand, imageLink, timestamp"  
    
    if not data_input_table.get("fields_str"):
        raise ErrorHandler("Нет значения в поле fields_str")
        # Эта ошибка не должна произойти

    order_string = data_input_table["fields_str"]


    ######################### Почему-то не сортируется как надо. Проверить


    # Разбиваем строку порядка на список полей, убираем пробелы
    field_order = [field.strip() for field in order_string.split(",")]

    # Убираем timestamp из порядка для сортировки value_field, так как он всегда в конце
    field_order_without_timestamp = [field for field in field_order if field != "timestamp"]

    # Разбиваем value_field на отдельные строки
    lines_list = value_field.split("\n")

    # Создаем словарь для быстрого поиска строк по имени поля
    field_to_line = {}
    other_lines = []  # Для строк, которые не соответствуют ожидаемому формату

    for line in lines_list:
        if line.strip():  # Пропускаем пустые строки
            # Пытаемся извлечь имя поля из строки (формат: "const fieldName = ...")
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "const":
                field_name = parts[1]
                field_to_line[field_name] = line
            else:
                other_lines.append(line)

    # Сортируем строки согласно порядку
    sorted_lines = []

    # 1. Добавляем строки в порядке field_order_without_timestamp
    for field in field_order_without_timestamp:
        if field in field_to_line:
            sorted_lines.append(field_to_line[field])
            # Удаляем из словаря, чтобы не добавлять повторно
            del field_to_line[field]

    # 2. Добавляем оставшиеся строки (которые не были в порядке)
    for remaining_line in field_to_line.values():
        sorted_lines.append(remaining_line)

    # 3. Добавляем строки, которые не соответствуют формату
    sorted_lines.extend(other_lines)

    # Формируем новый value_field
    sorted_value_field = "\n".join(sorted_lines)

    # Обновляем value_field
    value_field = sorted_value_field

    # Убираем табы слева у строки
    value_field = value_field.lstrip("\t")

    # Собираю поля для объекта item: исключаю триггеры, добавляю stock, timestamp
    other_keys = [k for k in result_selectors.keys() if k not in ("InStock_trigger", "OutOfStock_trigger")]

    ## Потому что приходящая строка полей уже будет отсортирована
    # # Сортируем поля в items_fields согласно order_string
    # # Создаем список для отсортированных полей
    # sorted_items_fields = []

    # # 1. Добавляем поля в порядке из field_order
    # for field in field_order:
    #     # Проверяем, есть ли поле в other_keys или это специальные поля
    #     if field in other_keys or field in ["stock", "timestamp", "link"]:
    #         sorted_items_fields.append(field)

    # # 2. Добавляем оставшиеся поля из other_keys, которых нет в field_order
    # for field in other_keys:
    #     if field not in sorted_items_fields and field not in ["stock", "timestamp", "link"]:
    #         sorted_items_fields.append(field)

    # # 3. Убеждаемся, что timestamp всегда в конце
    # if "timestamp" in sorted_items_fields:
    #     sorted_items_fields.remove("timestamp")
    #     sorted_items_fields.append("timestamp")

    # # Формируем строку с полями
    # items_fields = ", ".join(sorted_items_fields)

    template_parseCard = Template("""
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $$ = cheerio.load(data);

        $varFromSelector
        const timestamp = getTimestamp()

        const item: ResultItem = {
            $itemsFields
        }
        items.push(item);

        cacher.cache = items
        return items;
    }
    """)

    result = template_parseCard.substitute(
        itemsFields=order_string,
        varFromSelector=value_field,
    ).strip()

    # print(result)
    return result

    # # Сделал так, что форматирую код при создании
    # formatted = format_js(result)
    # print(formatted)
    # return formatted




# name, stock, link, price, oldprice, article, brand, imageLink, timestamp



# region Пример result_selectors
# # Пример использования 
# result_selectors = {
#     "name": [
#         "h1.name"
#     ],
#     "price": [
#         ".b"
#     ],
#     "oldprice": [
#         ".thr",
#         # ".thr2", ### Для теста
#     ],
#     "article": [
#         ".char > p:nth-of-type(1)"
#     ],
#     "brand": [
#         ".char > p:nth-of-type(2)"
#     ],
#     "InStock_trigger": [
#         ".nal.y"
#     ],
#     "imageLink": [
#         "html > body > section.wrap > main > article.wide > .card > .img_bl > .img > a.fancybox[href]"
#     ]
# }

################################## вызов для проверки (раскомментируйте для отладки)
# selector_checker_and_parseCard_gen(result_selectors, {"links": {"simple": [{"InStock_trigger": ".nal.y"}]}})

# Кэш для сгенерированного кода
_parse_card_code_cache = None

def get_parseCard_code(all_extracted_selectors):
    print(this_module_title)

    global _parse_card_code_cache
    # Генерируем код лениво, только когда он запрашивается
    # Это гарантирует, что data_input_table уже содержит fields_str
    if _parse_card_code_cache is None:
        # _parse_card_code_cache = selector_checker_and_parseCard_gen(result_selectors, data_input_table)
        _parse_card_code_cache = selector_checker_and_parseCard_gen(all_extracted_selectors, data_input_table)
    return _parse_card_code_cache
