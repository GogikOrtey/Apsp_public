### Извлечение селекторов

# Вынесенные отдельно функции
from addedFunc import *
from gen_data_input_table import data_input_table # Входные данные
from extracting_selector_from_html import * 
from saving_cache import * 

# Подключение всех библиотек
from import_all_libraries import * 
import copy

isPrint = False




this_module_title = """


------------------------------------------------------------------------------

                             EXTRACTION SELECTOR

------------------------------------------------------------------------------

"""



# region Обр. всех ссылок

# Обрабатываем все элементы из полученного массива - находим для каждого селектор
def fill_selectors_for_items(input_items, get_css_selector_from_text_value_element):
    items = input_items["links"]["simple"] # Проходимся по простым ссылкам
    # TODO В будущем доработать логику - возомжно здесь проходиться по всем массивам ссылок что есть
    host = ""

    
    print(f"Обработаем {len(items)} страниц")
    for item in items:
        # Если нет поля _selectors — создаём
        selectors = {}
        # html = get_html(item["link"]) # Получение html страницы напрямую, без кеша

        # Получаю страницу либо из кеша, либо запросом
        # Кешем, если она младше 18 часов
        # Используем глобальный кеш через get_html_from_cache
        html, data_time_str, timestamp_int = get_html_from_cache(item["link"], return_metadata=True)

        # Формирую элемент страницы, и добавляю его в переменную хранения всех страниц
        new_item = {
            "link": item["link"],
            "html_content": html,
            "data_time": data_time_str,   # Например: '05.11.2025 12:22'
            "timestamp": timestamp_int    # Например: 1760010122
        }
        content_html["simple"].append(new_item)

        # Извлекаю host, и изменяю imageLink
        if "imageLink" in item and item["imageLink"]:
            link_host = urlparse(item["link"]).scheme + "://" + urlparse(item["link"]).netloc
            image_host = urlparse(item["imageLink"]).scheme + "://" + urlparse(item["imageLink"]).netloc

            # Проверяем, совпадает ли host у ссылки, и ссылки на изображение
            if link_host == image_host:
                host = link_host  # максимум до третьего слеша
                item["_original_imageLink"] = item["imageLink"]
                item["imageLink"] = item["imageLink"].replace(host, "")
            else:
                host = link_host
        if input_items.get("host", "") == "" and host:
            print("🔵 host:", host)
            input_items["host"] = host

        # Проходим по всем ключам, кроме служебных и ссылки
        for key, value in item.items():
            # TODO Позже сделать условие покрасивее, пока что оставлю так
            if key.startswith("_") or key == "link":
                continue  # пропускаем служебные поля
            
            selector = ""
            # Обрабатываем только строки
            if isinstance(value, str) and value.strip():
                try:
                    is_price = False
                    # is_price = key in ("price", "oldprice")
                    ##################################################### Убрал. Проверить, стало ли стабильнее

                    # Две попытки: сначала exact=True, потом exact=False
                    # for attempt, is_exact in enumerate([True, False], start=1):
                    # TODO Это кажется костыль, упростить
                    # for attempt, is_exact in enumerate([False, True], start=1):


                    ################# Вот на это место обратить внимание, при отладке


                    for attempt, is_exact in enumerate([True, False], start=0):
                        selector = get_css_selector_from_text_value_element(
                            html, value, is_price=is_price, is_exact=is_exact
                        )
                        if selector:
                            # print(f"🟩 Найден селектор для поля {key}")
                            print(f"Найден селектор для поля {key}")
                            selector = selector.replace("div.", ".") ### Вот тут может быть ошибка
                            selectors[key] = selector                            
                            break  # если нашли — выходим из цикла
                        elif attempt == 1:
                            print(f"🟨 Не нашли при exact=True, пробуем частичным совпадением")

                    if not selector:
                        print(f"🟧 Не удалось найти селектор для поля {key} даже при exact=False")

                except Exception as e:
                    print(f"🟥 Ошибка при поиске селектора для {key}: {e}")
            else:
                print(f"⬜ Пропускаем поле {key}: Не строка или пустое значение")

        print("_______________________")


        # Записываем обратно
        item["_selectors"] = selectors




# region Результ. sel сайта

# Перебирает все селекторы которые мы собрали со всех страничек, 
# и выбирает наилучший, для каждого поля
def select_best_selectors(input_data, content_html):
    # TODO Не протестировал на селекторах, которые будут идти через запятую
    print_fail_report = True

    def normalize_text(s: str) -> str:
        if s is None:
            return ""
        s = re.sub(r"\s+", " ", s).strip()
        return s.lower()

    def extract_using_selector(tree: html_lx.HtmlElement, selector: str) -> str:
        """
        Пытается выполнить CSS селектор на дереве lxml и вернуть строковое значение.
        Поддерживает селекторы, которые указывают атрибут в конце вроде "[content]" или "[class]".
        Если несколько элементов — возвращает первый непустой результат.
        """
        selector = selector.strip()
        # попытка выделить атрибут в квадратных скобках в конце
        attr_match = re.search(r"\[([a-zA-Z0-9_\-:]+)\]\s*$", selector)
        attr = None
        if attr_match:
            attr = attr_match.group(1)
            # уберём этот кусок для передачи cssselect, если он стоял в конце как самостоятельный фрагмент
            # (но учти: селектор может легитимно содержать [..] внутри — мы учитываем только последний)
            # попробуем применить целиком сначала (на случай, если это часть сложного селектора)
            try:
                elems = tree.cssselect(selector)
            except Exception:
                # попробуем удалить последний [attr]
                selector_no_attr = selector[:attr_match.start()].rstrip()
                try:
                    elems = tree.cssselect(selector_no_attr)
                except Exception:
                    elems = []
        else:
            try:
                elems = tree.cssselect(selector)
            except Exception:
                elems = []

        for el in elems:
            # если указали attr и элемент имеет его — возвращаем
            if attr:
                val = el.get(attr)
                if val:
                    return val.strip()
            # если элемент — meta or input, попробуем стандартные атрибуты
            if el.tag in ("meta", "link", "img", "input"):
                # common attrs
                for a in ("content", "value", "alt", "src", "href", "data-src"):
                    v = el.get(a)
                    if v:
                        return v.strip()
            # иначе текстовое содержимое
            text = el.text_content()
            if text and text.strip():
                return text.strip()
        return ""

    def compute_match_score_2(expected: str, extracted: str) -> float:
        """Вычисляет процент совпадения строки с ожидаемым значением"""
        if not expected or not extracted:
            return 0.0
        
        expected_norm = normalize_text(expected)
        extracted_norm = normalize_text(extracted)
        
        # Если строки полностью совпадают
        if expected_norm == extracted_norm:
            return 1.0
        
        # Вычисляем процент вхождения ожидаемой строки в извлеченную
        if expected_norm in extracted_norm:
            return len(expected_norm) / len(extracted_norm)
        
        # Вычисляем процент вхождения извлеченной строки в ожидаемую
        if extracted_norm in expected_norm:
            return len(extracted_norm) / len(expected_norm)
        
        return 0.0

    def normalize_price(price_str: str) -> str:
        """Нормализация ценовой строки"""
        if not price_str:
            return ""
        # Удаляем все нецифровые символы, кроме точки и запятой
        normalized = re.sub(r"[^\d.,]", "", price_str)
        # Заменяем запятую на точку
        normalized = normalized.replace(",", ".")
        return normalized

    def resolve_selectors_across_examples(
            examples: List[Dict[str, Any]],
            fields: Iterable[str] = None,
            html_fetcher: Callable[[str], str] = None,
            verbose: bool = True,
        ) -> Dict[str, Any]:

        # Если fields не передан — определяем автоматически из примеров
        if not fields:
            if not examples:
                raise ValueError("Список examples пуст — невозможно определить поля автоматически.")
            # Собираем все уникальные поля из всех примеров
            all_fields = []
            for ex in examples:
                for k in ex.keys():
                    if k not in all_fields and k != "link" and not k.startswith("_"):
                        all_fields.append(k)
            fields = all_fields

        if verbose:
            print(f"Используемые поля: {fields}")

        """
        examples: список примеров, каждый пример - dict с keys: link, поля и _selectors dict
        возвращает: {
            "result_selectors": {field: [selector(s) chosen as list])},
            "report": {...}
        }
        """
        # 1) Собираем селекторы по полям
        selectors_by_field = defaultdict(list)
        for ex in examples:
            sdict = ex.get("_selectors", {})
            for f in fields:
                sel = sdict.get(f)
                if sel:
                    selectors_by_field[f].append(sel.strip())

        # уникализируем и считаем частоты
        counters = {f: Counter(selectors_by_field[f]) for f in fields}
        # сортировка кандидатов: по частоте desc, затем по длине asc
        candidates = {}
        for f, counter in counters.items():
            items = list(counter.items())
            items.sort(key=lambda t: (-t[1], len(t[0])))
            candidates[f] = [it[0] for it in items]

        if verbose:
            print("Кандидаты по полям (в порядке приоритета):")
            for f in fields:
                print(f" - {f}: {len(candidates[f])} селекторов -> {candidates[f]}")

        # 2) Подготовка html деревьев
        trees = []
        for ex in examples:
            url = ex["link"]
            html_text = html_fetcher(url)
            tree = html_lx.fromstring(html_text)
            trees.append((url, tree, ex))

        # 3) Проверяльщик: функция, которая проверяет набор селекторов (комбинацию) для одного поля
        def check_selector_set_for_field(field: str, sel_set: Tuple[str, ...]) -> bool:
            fails = 0
            total = 0

            for url, tree, ex in trees:
                expected = ex.get(field, "")
                sdict = ex.get("_selectors", {}) if isinstance(ex.get("_selectors", {}), dict) else {}
                if not expected or not sdict.get(field):
                    if verbose:
                        print(f"  [SKIP] {field} on {url}: no expected value or no original selector")
                    continue
                
                total += 1
                extracted_any = ""
                for s in sel_set:
                    got = extract_using_selector(tree, s)
                    if got:
                        extracted_any = got
                        break
                    
                score_match = compute_match_score_2(expected, extracted_any)
                if isPrint: 
                    print(f"score_match = {score_match} для '{expected}' и '{extracted_any}'")

                if field == "imageLink":
                    match_score_imageLink = similarity_percent_smart(expected, extracted_any)
                    if verbose:
                        if isPrint: print(f"match_score_imageLink = {match_score_imageLink}")

                    if match_score_imageLink >= 50:
                        score_match = 1
                match = score_match >= 0.8 or expected in extracted_any or extracted_any in expected or normalize_price(expected) == normalize_price(extracted_any)

                if not match:
                    if not expected and not extracted_any:
                        continue
                    
                    fails += 1
                    if verbose and print_fail_report:
                        print(f"[🟧 FAIL] {field} on {url}: ")
                        print(f"  искали: '{str(expected)[:200]}' ")
                        print(f"  нашли:  '{str(extracted_any)[:200]}' ")
                        print(f"  селектор: {str(sel_set)[:200]}")

            return fails == 0

        result_selectors = {}
        report = {"tried": {}}

        for field in fields:
            cand_list = candidates.get(field, [])
            report["tried"][field] = {"singles": [], "combinations": []}

            # Если селекторов 1 или 0 - старая логика
            if len(cand_list) <= 1:
                found = False
                for s in cand_list:
                    report["tried"][field]["singles"].append(s)
                    if check_selector_set_for_field(field, (s,)):
                        result_selectors[field] = [s]
                        found = True
                        break
                if not found:
                    result_selectors[field] = []
                    if verbose:
                        print(f"[WARN] Для поля {field} не найден селектор(ы).")
                continue

            # Если селекторов больше 1 - новая логика
            # Сначала пробуем найти селектор, который работает на всех страницах
            found_single_for_all = False
            for s in cand_list:
                report["tried"][field]["singles"].append(s)
                if check_selector_set_for_field(field, (s,)):
                    result_selectors[field] = [s]
                    found_single_for_all = True
                    break
            
            if found_single_for_all:
                continue
            
            # Если ни один селектор не работает на всех страницах
            # Собираем статистику по каждому селектору
            selector_stats = []
            
            for selector in cand_list:
                hits = 0  # сколько раз сработал
                total_with_expected = 0  # сколько страниц с ожидаемым значением
                total_score = 0.0  # суммарный процент совпадения
                
                for url, tree, ex in trees:
                    expected = ex.get(field, "")
                    if not expected:
                        continue
                        
                    total_with_expected += 1
                    extracted = extract_using_selector(tree, selector)
                    
                    if extracted:
                        hits += 1
                        # Вычисляем качество совпадения
                        if field in ("price", "oldprice"):
                            if normalize_price(expected) == normalize_price(extracted):
                                match_score = 1.0
                            else:
                                match_score = compute_match_score_2(expected, extracted)
                        else:
                            match_score = compute_match_score_2(expected, extracted)
                            
                            if field == "imageLink":
                                match_score_imageLink = similarity_percent_smart(expected, extracted)
                                if isPrint: print(f"match_score_imageLink = {match_score_imageLink}")
                                if match_score_imageLink >= 0.5:
                                    match_score = 1.0
                        
                        total_score += match_score
                
                if hits > 0:
                    avg_score = total_score / hits
                else:
                    avg_score = 0.0
                    
                selector_stats.append({
                    "selector": selector,
                    "hits": hits,
                    "total_pages": total_with_expected,
                    "avg_score": avg_score
                })
            
            # Фильтруем селекторы, которые сработали хотя бы раз
            working_selectors = [s for s in selector_stats if s["hits"] > 0]
            
            if not working_selectors:
                result_selectors[field] = []
                if verbose:
                    print(f"[WARN] Для поля {field} нет селекторов, которые сработали бы хоть раз.")
                continue
            
            # Сортируем: сначала по возрастанию количества срабатываний (реже = лучше),
            # затем по убыванию качества совпадения
            working_selectors.sort(key=lambda x: (x["hits"], -x["avg_score"]))
            
            # Формируем массив селекторов
            result_selectors[field] = [s["selector"] for s in working_selectors]
            
            if verbose:
                print(f"[INFO] Для поля {field} выбраны селекторы (по возрастанию частоты срабатывания):")
                for s in working_selectors:
                    print(f"  - {s['selector']}: сработал {s['hits']} из {s['total_pages']}, качество: {s['avg_score']:.2f}")

        return {"result_selectors": result_selectors, "report": report}

    def make_html_fetcher_from_cache(content_html):
        """
        Возвращает функцию html_fetcher(link),
        которая достаёт html_content из заранее сохранённого словаря content_html
        """
        html_map = {}
        for group in content_html.values():
            for item in group:
                link = item.get("link", "").strip()
                html_text = item.get("html_content", "")
                if link and html_text:
                    html_map[link] = html_text

        def fetcher(url):
            if url in html_map:
                return html_map[url]
            raise ValueError(f"HTML для {url} не найден в content_html")

        return fetcher

    # создаём html_fetcher на основе кеша, из сохранённых html страничек
    html_fetcher = make_html_fetcher_from_cache(content_html)

    # вызываем основной алгоритм
    result = resolve_selectors_across_examples(
        input_data,
        html_fetcher=html_fetcher,
        verbose=True
    )

    # Убираем преобразование в строку через запятую, возвращаем массив
    # (как и требуется в задании)
    
    # Сохраняем страницы в кеш и обновляем глобальный кеш
    save_content_html_to_cache(content_html)
    # Обновляем глобальный кеш после сохранения
    global global_cache
    global_cache = load_cache()

    return result










### Тест одного селектора с одной страницы
# region Тест 1 элемента







# isPrint = True

# elem_number = 0
# html = get_html( data_input_table["links"]["simple"][elem_number]["link"])
# # print(html[:500])

# # substring = data_input_table["links"]["simple"][elem_number]["name"]
# # substring = data_input_table["links"]["simple"][elem_number]["price"]
# substring = data_input_table["links"]["simple"][elem_number]["oldprice"]
# # substring = data_input_table["links"]["simple"][elem_number]["brand"]
# # substring = data_input_table["links"]["simple"][elem_number]["article"]
# # substring = data_input_table["links"]["simple"][elem_number]["imageLink"]
# # substring = "/upload/dev2fun.imagecompress/webp/iblock/81e/yypuhdwg8uf7jtktf65opgzc4wthjo6w.webp"

# selector_result = get_css_selector_from_text_value_element(html, substring)
# # selector_result = get_css_selector_from_text_value_element(html, substring, is_price = True)
# # selector_result = get_css_selector_from_text_value_element(html, substring, is_exact=False)
# # selector_result = get_css_selector_from_text_value_element(html, substring, is_exact=True)

# print("")
# print(f"🟩 selector_result = {selector_result}")








# # Проверка сложных селекторов

# # Извлекаем HTML из первой страницы словаря content_html
# html_text = content_html['simple'][0]['html_content'] if content_html.get('simple') and len(content_html['simple']) > 0 else ''
# # result_new_selector = get_element_from_selector_universal(html_text, 'tr:has(td:contains("Производитель/Бренд")) td:nth-child(2)')
# hard_selector = '#characteristic > .show-more-block > table.table tr:has(td:contains("Артикул")) > td:nth-child(2)'
# result_new_selector = get_element_from_selector_universal(html_text, hard_selector)
# print("result_new_selector = " + result_new_selector)











# region Обр. всех sel

def get_all_selectors(data_input_table):
    print(this_module_title)

    # keep original input values safe from in-place mutations (e.g., imageLink)
    ################################### Вот тут создаю резервную копию, и потом восстанавливаю из неё
    data_input_table_backup = copy.deepcopy(data_input_table)

    fill_selectors_for_items(
        data_input_table,
        get_css_selector_from_text_value_element
    )

    # print_json(data_input_table["links"]["simple"])

    result_select_best_selectors = select_best_selectors(data_input_table["links"]["simple"], content_html)
    # print("content_html =", str(content_html)[:1000])

    print("")
    print("")
    print("✅ Итоговые селекторы:")
    print_json(result_select_best_selectors["result_selectors"])

    # Сохраняю в резервную копию, и загружаю из неё после обработки массив входных значений
    # потому что там у меня меняется например значения для поля imageLink
    data_input_table.clear()
    data_input_table.update(data_input_table_backup)

    return result_select_best_selectors["result_selectors"]




########################################### Вот эту строчку раскомментировать, для запуска
# get_all_selectors(data_input_table) 
