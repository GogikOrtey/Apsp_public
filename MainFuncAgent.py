### Основной скрипт агента

# Вынесенные отдельно функции
from addedFunc import *
from gen_data_input_table import data_input_table # Входные данные
from extracting_selector_from_html import * 

# Подключение всех библиотек
from import_all_libraries import * 

isPrint = False

# Здесь остался только функционал для сбора селекторов с сайта, и генерации parsePage
# генерацию - только начал писать
# Кстати её наверное стоит вынести также в отдельный файл


# region Check html
# Проверяю, что html-страница доступна, и данные первого товара на ней есть
def check_avialible_html():
    # TODO: Потом добавить обработку, что бы он искал не полным сравнением подстроки названия товара при проверке, а частичным
    # Это когда напишу такую штуку для price

    first_item_link = data_input_table["links"]["simple"][0]["link"]
    # print(first_item_link)
    html = get_html(first_item_link)
    # print(html[:500])

    text_includes = data_input_table["links"]["simple"][0]["name"] 
    if text_includes in html:
        # print("🟢 Подстрока найдена!")
        a = 1
    else:
        print("🟠 Подстрока не найдена.")
        raise ErrorHandler("При открытии страницы 1 товара, на ней не было обнаружено названия товара", "4-1")

# Проверяю, что html-страница доступна, и данные первого товара на ней есть
check_avialible_html()


# region Обр. всех ссылок

# Обрабатываем все элементы из полученного массива - находим для каждого селектор
def fill_selectors_for_items(input_items, get_css_selector_from_text_value_element):
    items = input_items["links"]["simple"] # Проходимся по простым ссылкам
    # TODO В будущем доработать логику - возомжно здесь проходиться по всем массивам ссылок что есть
    host = ""
    cache = load_cache()
    
    print(f"Обработаем {len(items)} страниц")
    for item in items:
        # Если нет поля _selectors — создаём
        selectors = {}
        # html = get_html(item["link"]) # Получение html страницы напрямую, без кеша

        # Получаю страницу либо из кеша, либо запросом
        # Кешем, если она младше 18 часов
        html, data_time_str, timestamp_int = get_html_with_cache(item["link"], cache)

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
                    is_price = key in ("price", "oldPrice")

                    # Две попытки: сначала exact=True, потом exact=False
                    for attempt, is_exact in enumerate([True, False], start=1):
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

    def resolve_selectors_across_examples(
            examples: List[Dict[str, Any]],
            fields: Iterable[str] = None,
            html_fetcher: Callable[[str], str] = None,
            max_combination_size: int = None,
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
                    
                # 💡 Обработка ценовых полей
                if field in ("price", "oldPrice"):
                    match = normalize_price(expected) == normalize_price(extracted_any)
                else:
                    # # match = normalize_text(expected) == normalize_text(extracted_any)
                    # # match = compute_match_score(expected, extracted_any) >= 0.7
                    # score_match = compute_match_score(expected, extracted_any)
                    score_match = compute_match_score_2(expected, extracted_any)
                    if(field == "imageLink"): # Пониженный порог соответствия для imageLink
                        print(f"score_match imageLink = {score_match}")
                        if score_match >= 0.5:
                            score_match = 1
                    match = expected in extracted_any or extracted_any in expected or score_match >= 0.8

                if not match:
                    if not expected and not extracted_any:
                        continue
                    
                    fails += 1
                    if verbose and print_fail_report:
                        print(f"[🟧 FAIL] {field} on {url}: ")
                        print(f"  искали: '{str(expected)[:200]}' ")
                        print(f"  нашли:  '{str(extracted_any)[:200]}' ")
                        print(f"  селектор: {str(sel_set)[:200]}")
                        # print(f"  score_match = '{score_match:.3f}' ")                        

            return fails == 0

        result_selectors = {}
        report = {"tried": {}}

        # лимит на размер комбинаций
        n_examples = len(examples)
        if max_combination_size is None:
            max_combination_size = n_examples - 1  # если равен n_examples => ошибка по условию

        for field in fields:
            cand_list = candidates.get(field, [])
            report["tried"][field] = {"singles": [], "combinations": []}

            # сначала пробуем одиночные селекторы в порядке приоритета
            found = False
            for s in cand_list:
                report["tried"][field]["singles"].append(s)
                if check_selector_set_for_field(field, (s,)):
                    result_selectors[field] = [s]
                    found = True
                    break
            if found:
                continue

            # если одиночные не прошли — пробуем комбинации размера 2..max_combination_size
            # Перебираем комбинации из кандидатов (если кандидатов мало, то возможны все комбинации)
            for size in range(2, max_combination_size + 1):
                if size > len(cand_list):
                    break
                if verbose:
                    print(f"Пробуем комбинации size={size} для поля {field} (всего {len(cand_list)} кандидатов)")
                ok = False
                # ограничим число комбинаций, чтобы не взорвать время: если кандидатов много — используем лучшую часть
                max_cands_for_comb = 12
                use_candidates = cand_list[:max_cands_for_comb] if len(cand_list) > max_cands_for_comb else cand_list
                for combo in itertools.combinations(use_candidates, size):
                    report["tried"][field]["combinations"].append(combo)
                    if check_selector_set_for_field(field, combo):
                        result_selectors[field] = list(combo)
                        ok = True
                        break
                if ok:
                    found = True
                    break

            if not found:
                # если минимальный возмож размер равен числу примеров -> это ошибка
                if max_combination_size >= n_examples:
                    raise RuntimeError(f"Для поля '{field}' не найден валидный набор селекторов; "
                                       f"минимальный размер комбинации достиг {n_examples} — селекторы вероятно неверные.")
                else:
                    # оставляем пустой и отчётим
                    result_selectors[field] = []
                    if verbose:
                        print(f"[WARN] Для поля {field} не найден селектор(ы).")

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

    # Собираю результаты селекторы по каждому полю в строку, через запятую
    for key, value in result["result_selectors"].items():
        if isinstance(value, list):
            result["result_selectors"][key] = ", ".join(value) if value else ""

    # Сохраняем страницы в кеш
    save_content_html_to_cache(content_html)

    return result

# region Сохранение кеша

CACHE_FILE = "cache.json"
MAX_AGE_HOURS = 18

def load_cache(file=CACHE_FILE):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"simple": []}

# Получаем html, проверяя кеш
def get_html_with_cache(link, cache):
    now = int(time.time())
    # Ищем страницу в кеше
    for item in cache["simple"]:
        if item["link"] == link:
            age_hours = (now - item["timestamp"]) / 3600
            if age_hours <= MAX_AGE_HOURS:
                print(f"📤 Берем страницу из кеша: {link} (возраст {age_hours:.2f} ч.)")
                return item["html_content"], item["data_time"], item["timestamp"]
            break  # страница есть, но устарела — выйдем и загрузим заново

    # Если страницы нет в кеше или она старая — получаем заново
    html = get_html(link) 
    data_time_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    timestamp_int = int(time.time())

    # Обновляем или добавляем в кеш
    updated = False
    for item in cache["simple"]:
        if item["link"] == link:
            item.update({
                "html_content": html,
                "data_time": data_time_str,
                "timestamp": timestamp_int
            })
            updated = True
            break
    if not updated:
        cache["simple"].append({
            "link": link,
            "html_content": html,
            "data_time": data_time_str,
            "timestamp": timestamp_int
        })

    return html, data_time_str, timestamp_int

# Сохраняет загруженные страницы в кеш
def save_content_html_to_cache(content_html, cache_file="cache.json"):
    """
    Сохраняет content_html в JSON файл, обновляя существующие записи по ссылке.
    Удаляет записи старше 2 недель.
    Выводит сколько страниц добавлено, обновлено и удалено.
    """
    # Загружаем существующий кеш
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            try:
                existing_cache = json.load(f)
            except json.JSONDecodeError:
                existing_cache = {"simple": []}
    else:
        existing_cache = {"simple": []}

    # Словарь для быстрого поиска по link
    existing_map = {item["link"]: item for item in existing_cache.get("simple", [])}

    added_count = 0
    updated_count = 0

    # Timestamp для двух недель назад
    two_weeks_ago = int(time.mktime((datetime.now() - timedelta(weeks=2)).timetuple()))

    # Собираем ссылки новых элементов для быстрого поиска
    new_links_set = set()

    # Обновляем или добавляем новые записи
    for new_item in content_html.get("simple", []):
        link = new_item.get("link")
        if not link:
            continue
        new_links_set.add(link)
        if link in existing_map:
            updated_count += 1
        else:
            added_count += 1
        existing_map[link] = new_item

    # Удаляем старые записи, которые не были обновлены
    to_delete = [link for link, item in existing_map.items()
                 if item["timestamp"] < two_weeks_ago and link not in new_links_set]
    for link in to_delete:
        del existing_map[link]

    deleted_count = len(to_delete)

    # Преобразуем обратно в список
    updated_cache = {"simple": list(existing_map.values())}

    # Сохраняем в файл
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(updated_cache, f, ensure_ascii=False, indent=2)

    print(f"\n📄 Кеш сохранён в {cache_file}, всего страниц: {len(updated_cache['simple'])}")
    print(f"   Добавлено: {added_count}, обновлено: {updated_count}")
    if deleted_count:
        print(f"   Удалено старых страниц: {deleted_count}")












### Тест одного селектора с одной страницы
# region Тест 1 элемента







isPrint = True

elem_number = 0
html = get_html( data_input_table["links"]["simple"][elem_number]["link"])
# print(html[:500])

# substring = data_input_table["links"]["simple"][elem_number]["name"]
# substring = data_input_table["links"]["simple"][elem_number]["price"]
# substring = data_input_table["links"]["simple"][elem_number]["oldPrice"]
# substring = data_input_table["links"]["simple"][elem_number]["brand"]
substring = data_input_table["links"]["simple"][elem_number]["article"]
# substring = data_input_table["links"]["simple"][elem_number]["imageLink"]
# substring = "/upload/dev2fun.imagecompress/webp/iblock/81e/yypuhdwg8uf7jtktf65opgzc4wthjo6w.webp"

# selector_result = get_css_selector_from_text_value_element(html, substring)
# selector_result = get_css_selector_from_text_value_element(html, substring, is_price = True)
selector_result = get_css_selector_from_text_value_element(html, substring, is_exact=False)
print("")
print(f"🟩 selector_result = {selector_result}")











# # region Обр. всех sel

# fill_selectors_for_items(
#     data_input_table,
#     get_css_selector_from_text_value_element
# )

# print_json(data_input_table["links"]["simple"])

# result_select_best_selectors = select_best_selectors(data_input_table["links"]["simple"], content_html)

# print("")
# print("")
# print("✅ Итоговые селекторы:")
# print_json(result_select_best_selectors["result_selectors"])





















# region Создаю parseCard

"""
Проверяет, что все селекторы действительно извлекают то что нужно
И если нужно, то собирает код, который правит их результаты, или как-то
по другому обрабатывает (через агента генерации кода)


Если InStock_trigger и OutOfStock_trigger - одинаковые, то
используем проверку на InStock_trigger, а по умолчанию оставляем занчение "OutOfStock"

Проверить, если ImageLink собирается без хоста, то добавить хост

Использует автоформаттер для price и oldPrice
Проверяет, что итоговые значения корректны
    Простейшая проверка - попробовать пройтись parseInt
    const price = $(".b").text().trim().formatPrice()

##### ChatGPT Agent usage
Далее, здесь будут проверяться все значения на ситуации по типу: Например значение артикула может собираться как: "Артикул: 112233"
    а нам нужно собрать только "112233"

"""



# Собирает финальный код для вставки в шаблон
def selector_checker_and_parseCard_gen(result_selectors, data_input_table):
    print("Проверяем селекторы, и генерируем parseCard")
    print_json(result_selectors)

    # Проверка на наличие всех необходимых полей, и селекторов для них
    # Обязательно должны присутствовать поля и селекторы для: name, stock, price
    value_field = ""
    result_stock_selector = ""

    # Собираем все подстроки, которые триггерят InStock 
    all_inStock_selectors = {elem.get("InStock_trigger") for elem in data_input_table["links"]["simple"] if elem.get("InStock_trigger")}
    count_of_unical_text_selectors = len(all_inStock_selectors)

    if count_of_unical_text_selectors == 1:
        all_inStock_selectors_js = f'"{next(iter(all_inStock_selectors))}"'
    else:
        all_inStock_selectors_js = "[" + ", ".join(f'"{x}"' for x in all_inStock_selectors) + "]"

    def using_InStock_triggers_value(result_selectors, use_OutOfStock = False):
        key_stock = "InStock_trigger" if use_OutOfStock == False else "OutOfStock_trigger"
        result_if_stock = '"InStock" : "OutOfStock"' if use_OutOfStock == False else '"OutOfStock" : "InStock"'
        if count_of_unical_text_selectors == 1:
            result_stock_selector = (
                f'const stock = $("{result_selectors[key_stock]}")'
                f'.text()?.includes({all_inStock_selectors_js}) ? {result_if_stock}'
            )
        else:
            result_stock_selector = (
                f'const stock = {all_inStock_selectors_js}.some(s => $("{result_selectors[key_stock]}")'
                f'.text()?.includes(s)) ? {result_if_stock}'
            )
        return result_stock_selector

    # Обработка логики наличия
    if "InStock_trigger" not in result_selectors and "OutOfStock_trigger" not in result_selectors:
        print("Нет триггеров наличия, считаем что все товары в наличии")
        result_stock_selector = 'const stock = "InStock"\n'
    elif "InStock_trigger" in result_selectors and "OutOfStock_trigger" in result_selectors:
        print("Оба триггера есть")
        if result_selectors["InStock_trigger"] == result_selectors["OutOfStock_trigger"]:
            print("Они одинаковые, используем InStock")
            result_stock_selector = using_InStock_triggers_value(result_selectors)
    elif "InStock_trigger" in result_selectors and not "OutOfStock_trigger" in result_selectors:
        print("Есть только триггер InStock, используем его")
        result_stock_selector = using_InStock_triggers_value(result_selectors)
    elif "InStock_trigger" not in result_selectors and "OutOfStock_trigger" in result_selectors:
        print("Есть только триггер OutOfStock, используем его")
        result_stock_selector = using_InStock_triggers_value(result_selectors, use_OutOfStock = True)

    value_field += f"{result_stock_selector}\n"



    # OutOfStock_trigger в полях прописывается, их нужно чистит от этих объектов
    # и заменять на stock


    # В конце
    value_field = value_field.rstrip("\n")

    # Собираю поля
    items_fields = ", ".join(result_selectors.keys()) + ", timestamp"

    template_parseCard = Template("""
    async parseCard(set: SetType, cacher: Cacher<ResultItem[]>) {
        let items: ResultItem[] = []

        const data = await this.makeRequest(set.query);
        const $$ = cheerio.load(data);

        $varFromSelector
        const link = set.query
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
        itemsFields=items_fields,
        varFromSelector=value_field,
    )

    print(result)
    return result


















# Для примера
result_selectors = {
    "name": "h1.name",
    "price": ".b",
    "article": ".char > p",
    "brand": "li:nth-of-type(4) > a",
    "InStock_trigger": ".nal.y",
    "imageLink": "a.fancybox[href]",
    "oldPrice": ".thr"
}


# selector_checker_and_parseCard_gen(result_selectors, data_input_table)






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




    # Добавить подсказку о версии APSP, который его создал







# # result_file_JS(result_selectors, "https://megapteka.ru/basket")
# result_file_JS(result_selectors, "https://www.perekrestok.ru/cat/")


































"""
    🟩 selector_result = 
    div.catalog-element-panel-gallery-picture.intec-ui-picture.intec-image-effect > img[src]

    ['.catalog-products-viewed-image-wrapper.intec-ui-picture > img[src]', 
     '.catalog-element-panel-gallery-picture.intec-ui-picture.intec-image-effect > img[src]']

    Нужно добавить в сортировку результатов - сортировку по расположению
    Например, если селектор обнаружился после половины страницы, либо после 2/3,
    то его мы отправляем в конец, согласно сортировке по возрастанию длины
    Это уже в конце, после всех остальных сортировок

    И добавить вывод всех найденных селекторов, в виде массива, уже отсортированные, что бы я видел что их чего выбирается

    Эта проблема кажется на 7м сайте была замечена, когда APSP собирает селекторы из
    блока "Просмотренное", потому что там данные совпадают, и селекторы короче
"""




"""


7й сайт не очень отрабатывает
Тестировать на других сайтах
    Можно тестировать на сайтах для ЗКС (в целом, это и делаю)
    https://elize.ru/shop/product_real/105070/

    https://stroytorg812.ru/catalog/sanitarnaya_keramika/unitaz_podvesnoy_brasko_smart_bezobodkovyy_sidene_slim_dyuroplast_mikrolift/

На 8м сайте уделить внимание поля article и brand
    У article - текст нужно извлекать, а также он - первый элемент. Дети и потомки не нужны
    ChatGPT должен корректно это обработать, если ему скинуть пример


11й сайт отрабатывает плохо, по поиску селекторов
    Оказывается, старая цена рассчитывается на сайте, а не приходит




* Идея: Можно из страницы извлекать весь текст
    * Затем скармливать нейронке, и просить локализовать фразу, которую мы ищем - например, пагинацию, или установку региона
    * Далее, ищем эту фразу в полном html файле, берём +1000 и -1000 символов, и снова загоняем в нейронку
    * и просим её дать селектор для извлечения этого элемента
    * Далее - тестируем, и если ок, то оставляем
    * Назовём эту процедуру: AI_selector_extractor

* Также всё таки наверное можно будет сделать так, что мы кидаем ссылку на сайт
    * Он открывается во внутреннем браузере
    * ИИ собирает краткую семантику сайта
    * ИИ ищет поле ввода
    * Вводит туда несколько запросов
        * На каждом находит пагинацию, и переходит на 2ю страницу
        * и фактически - извлекает нужные нам данные
        * А затем переходит на карточки товаров, и собирает данные с них (но тут уже хз)


    



    
Тогда глобальные задачи:

* parsePage
    * Добавить обработку извлечения пагинации - как номера страниц
    * Объединить логику извлечения host
    * Там в одном месте табов слишком мало перед строкой получается, это исправить
    
    * Более сложные задачи, выполнить позже:
        * Добавить обработку сохранения данных о товаре без отправки parseCard, если все нужные данные есть
        * Добавить сбор с дигинетики (когда подключим внутренний браузер, и сможем смотреть запросы)
        * Добавить обработку страниц с бесконечной подгрузкой (она будет через запросы в браузере)

* parseCard
    * Если у селектора больше 1 результата, то добавлять .first() в путь. Выписать отдельную проверку для этого
    * Протестировать новую логику сортировки селекторов по его позиции
    * Вынести всю логику генерации функции parseCard отдельно
    * Логику заполнения шаблона только начал прописывать
    * ...
    * Уделить внимание обработке price
    * Если изображение получается без хоста, и мы его добавляем, то также добавить проверку что он корректен    
    * По новым отдельным функциям (позже)
        * json_data_handler
            * Написать отдельный модуль по извлечению и парсингу JSON, внутри главной html страницы
              т.е. смотреть и искать json-фрагменты на странице, если найдены - то пытаться найти в них искомые элементы
        * all_characteristic_handler
            * Будет детектить и писать функцию (используя ИИ), для извлечения всех характеристик, из таблицы на странице товара
            * И далее надо будет смотреть, если какие-то характеристики нужны как поля, то можно брать от туда
              Но это надо будет дополнительно протестить

* global_code
    * Собирает код, используя готовые куски кода parseCard, parsePage и makeRequest
    * Возможно валидирует его, на предмет синтаксических ошибок в JS 

* MainFuncAgent
    * Это будет скрипт, который собирает финальный код парсера
    * В нём будут все нужные функции вызываться последовательно, и в результате будет генерация итогового файла кода
    * Как всё будет работать:
        * parseCard - генерирует кусок кода для parseCard
        * parsePage - генерирует кусок кода для parsePage
        * makeRequest - генерирует кусок кода для parsePage
        * global_code - собирает итоговый шаблон кода, на основе parseCard, parsePage и makeRequest
    * И сохраняет результирующий код парсера в файл
    * Подумать над тем, нужно ли будет генерировать также и файл конфигурации для парсера        

* Также нужно найти рабочий api для бесплатного использования ИИ, вместо платного YandexGPT
    * Либо, если не найду, развренуть ИИ на своём синем компе, и настроить что бы с рабочего ноута на него проходили запросы

* И тестировать на сайтах, которые давали аутсорсерам
    
* Написать AI_selector_extractor
    * Извлечение текста страницы, без тегов
    * Скармливание его ИИ, ищем нужное слово
    * Затем ищем его в html 
    ... (расписал выше)
    


























    
* Тестирование
    * Сделать отдельный файлик для автотестов
    * Написать автотесты для каждого большого модуля
    * Для этого использовать только кешированные html странинцы (или их в первую очередь)
    * Написать автотесты для всех сайтов, что у меня сейчас есть в коллекции
        * И прописать что бы он выводил красивый и читаемый отчёт о том, что в ответах изменилось

* makeRequest
    * Создать отдельный скрипт makeRequest_generate
    * Изначально пускай использует шаблон-заглушку
    * Там нужно будет проверить
        * Спросить у CG что конкретно здесь нужно обработать
        * ...
        * Получаются ли данные вообще -> есть ли защита
        * С какими прокси работает (tor.ru, tor.eu, fine.org, fine.ru, squid)
        * С каким движком работает (все 3)
        * Если есть защита, то работает ли с flaresolver
            * Если режим flaresolver помогает, то будет ли работать сохранение кук, и запросы через normal mode 
              При сохранении кук, не забыть прописать сохранение покси и ua
              И процедуру для их сброса
        Всё это нужно будет использовать через curl запросы





        













————————————————————————

Далее:

* check_content_in_browser
    * Будет открывать страницу в браузере, и смотреть все запросы, которые туда приходят
    * И искать во всех запросах данные о товаре. Если был надйен запрос, то попробует извлечь из него json
      провалидировать и использовать данные из него
    * И повторить этот запрос через curl

* Нужно будет собрать форму (например в Yandex Forms), с последовательным заполнением полей
  которая на выходе будет генерировать json-файл для АПСП

* Далее можно добавить обработку регионов
    * Регионы могут задаваться через поддомен
    * Или через параметр в куках
    * Также редко - через параметр в запросе
    * И надо что бы он добавлял регионы с описанием, в формате "12;Екатеринбург"
    * Самое тяжёлое - это будет найти на странице, где можно поменять регион

* Также можно будет попробовать автоматизировать парсинг вариаций товара (парфюмерия)
    * Но там часто по разному, и что-то одно собрат будет сложно
      можно будет капитально подключить ИИ агента
    * Ещё есть кейсы, когда у одного товара несколько цен (автомобильные)
      там нужно будет генерировать уникальные ссылки с #



























Нужно будет прогнать весь код через нейронку, что бы она почистила код, собрала нужные функции вместе
Просмотрела на наличие возможных ошибок
И уязвимостей



Далее тестирую на существующих парсерах
и на больших, типо WB 
И можно будет презентовать проект директору

"""