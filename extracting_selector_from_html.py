# Здесь собраны все функции, нужные для того что бы получить лучший селектор текстового элемента, из переданного html
# Можно использовать так: 
# selector_result = get_css_selector_from_text_value_element(html, substring)

# Подключение всех библиотек
from import_all_libraries import * 

isPrint = False

# region Доп. методы

def print_json(input_json):
    text = json.dumps(input_json, indent=4, ensure_ascii=False)
    text = text.replace('\\"', '"')
    print(text)

def clean_html(text: str) -> str:
    if not text:
        return ""
    text = text.replace("&nbsp;", " ").replace("\xa0", " ")
    text = re.sub(r"[\u200b\u200e\u200f\r\n\t]+", " ", text)
    return text.strip()

def normalize_price(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = clean_html(s)
    s = re.sub(r"[^\d,\.]", "", s)
    s = re.sub(r"[^\d]", "", s)
    return s

# Вспомогательная функция для оценки схожести
def compute_match_score(found_text, target_text):
    """Оценка схожести строк по количеству совпадающих символов"""
    found_text = found_text.strip().lower()
    target_text = target_text.strip().lower()

    if not found_text or not target_text:
        return 0.0

    # Длина совпадающих символов (по порядку)
    common = sum(1 for a, b in zip(found_text, target_text) if a == b)
    score = common / max(len(target_text), len(found_text))
    return score

from difflib import SequenceMatcher

# Сравнение перестановками. Сравнивает строки более точно
def compute_match_score_2(found_text, target_text):
    found_text = found_text.strip().lower()
    target_text = target_text.strip().lower()

    if not found_text or not target_text:
        return 0.0

    return SequenceMatcher(None, found_text, target_text).ratio()

# TODO Можно заменить compute_match_score на compute_match_score_2, если будет работать ок

# Здесь хранятся html страницы (типо кеша)
content_html = {
    "simple": [
        # {
        #     "link": "",
        #     "html_content": ""  
        # },    
    ]
}


# region Поиск селекторов
def find_text_selector(
    html: str,
    text: str,
    exact: bool = True,
    return_all_selectors: bool = False,
    isPriceHandle: bool = False,
    allow_complex_classes: bool = False  # Использовать ли сложные аттрибуты, типо [class*="..."]
):
    # Игнорируем атрибуты, содержащие эти подстроки, при поиске css пути
    IGNORED_SUBSTRS = ["data", "src", "href", "alt", "title", "content", "title"]
    PRIORITY_ATTRS = ["name", "property", "itemprop", "id"]

    if isPriceHandle:
        html = clean_html(html)
        text = normalize_price(text)

    DANGEROUS_CHARS = set(':[]/%%()#') 

    def class_is_dangerous(cls: str) -> bool:
        if not cls:
            return False
        # Класс содержит опасные символы
        if any(ch in cls for ch in DANGEROUS_CHARS):
            return True
        # Класс содержит кавычки или пробел
        if '"' in cls or "'" in cls or " " in cls:
            return True
        # Класс начинается с цифры
        if cls[0].isdigit():
            return True
        return False

    def escape_attr_value(val: str) -> str:
        return val.replace('"', '\\"')

    def get_css_path(element):
        path = []
        while element and element.name and element.name != "[document]":
            selector = element.name

            # Если есть id — используем его
            if element.has_attr("id"):
                selector = f"#{element['id']}"
                path.append(selector)
                break

            # Классы
            if element.has_attr("class"):
                cls_parts = []
                for cls in element.get("class", []):
                    if not cls:
                        continue
                    # если класс опасный
                    if class_is_dangerous(cls):
                        if allow_complex_classes:
                            cls_parts.append(f'[class*="{escape_attr_value(cls)}"]')
                        else:
                            continue  # ❌ пропускаем опасные классы
                    else:
                        cls_parts.append(f'.{cls}')
                selector += "".join(cls_parts)

            # Проверяем наличие значимых атрибутов
            has_significant_attr = any(
                (
                    attr in PRIORITY_ATTRS or not any(sub in attr for sub in IGNORED_SUBSTRS)
                )
                for attr in element.attrs.keys()
            )

            if not has_significant_attr:
                siblings = element.find_previous_siblings(element.name)
                if siblings:
                    selector += f":nth-of-type({len(siblings) + 1})"

            path.append(selector)
            element = element.parent

        return " > ".join(reversed(path))

    def normalize_text(s):
        return " ".join(s.split())

    def similarity(a, b):
        return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()

    def make_selector(el, base_selector, attr_name):
        parts = [base_selector]
        is_ignored = any(sub in attr_name for sub in IGNORED_SUBSTRS)

        element_id = el.get("id")
        has_id_in_base = element_id and f"#{element_id}" in base_selector

        if is_ignored:
            for alt_attr in PRIORITY_ATTRS:
                if el.has_attr(alt_attr):
                    if alt_attr == "id" and has_id_in_base:
                        continue
                    val = el.get(alt_attr)
                    if isinstance(val, list):
                        val = " ".join(val)
                    if isinstance(val, str):
                        parts.append(f'[{alt_attr}="{escape_attr_value(val.strip())}"]')
                    break
            parts.append(f'[{attr_name}]')
        else:
            val = el.get(attr_name)
            if isinstance(val, list):
                val = " ".join(val)
            if isinstance(val, str):
                if attr_name == "id" and has_id_in_base:
                    return "".join(parts)
                parts.append(f'[{attr_name}="{escape_attr_value(val.strip())}"]')
            else:
                parts.append(f'[{attr_name}]')

        return "".join(parts)

    # --- Парсим HTML ---
    soup = BeautifulSoup(html, "html.parser")
    selectors = []

    # --- Основной поиск (точное совпадение) ---
    for el in soup.find_all(True):
        element_text = el.get_text(strip=True)
        if element_text:
            check_value = normalize_price(element_text) if isPriceHandle else element_text
            match = (text == check_value) if exact else (text in check_value)
            if match:
                selector = get_css_path(el)
                if return_all_selectors:
                    selectors.append(selector)
                else:
                    return selector

        for attr_name, attr_val in el.attrs.items():
            if isinstance(attr_val, list):
                attr_val = " ".join(attr_val)
            if isinstance(attr_val, str):
                check_value = normalize_price(attr_val) if isPriceHandle else attr_val
                match = (text == check_value) if exact else (text in check_value)
                if match:
                    base_selector = get_css_path(el)
                    selector = make_selector(el, base_selector, attr_name)
                    if return_all_selectors:
                        selectors.append(selector)
                    else:
                        return selector

    # --- Нестрогий поиск ---
    if not selectors:
        threshold = 0.7
        for el in soup.find_all(True):
            element_text = el.get_text(strip=True)
            if element_text:
                check_value = normalize_price(element_text) if isPriceHandle else element_text
                score = similarity(text, check_value)
                if score >= threshold:
                    selector = get_css_path(el)
                    if return_all_selectors:
                        selectors.append(selector)
                    else:
                        return selector

            for attr_name, attr_val in el.attrs.items():
                if isinstance(attr_val, list):
                    attr_val = " ".join(attr_val)
                if isinstance(attr_val, str):
                    check_value = normalize_price(attr_val) if isPriceHandle else attr_val
                    score = similarity(text, check_value)
                    if score >= threshold:
                        base_selector = get_css_path(el)
                        selector = make_selector(el, base_selector, attr_name)
                        if return_all_selectors:
                            selectors.append(selector)
                        else:
                            return selector

    if return_all_selectors:
        return selectors if selectors else None
    return None


# region Выбирает один sel

# # Основная функция: Получает css селектор, по текстовому содержанию элемента
# # Эта функция get_css_selector_from_text_value_element получает на вход один элемент
# # Отправляет его в find_text_selector - получает набор css селекторов к этому элементу
# # Проверяет, что каждый селектор действительно верный, и сортирует их по точности совпадения
# # также сортирует по длине, чем короче тем лучше
# # Затем, найденный лучший селектор - дистиллирует
# def get_css_selector_from_text_value_element(html, finding_element, is_price = False, is_exact = True, is_multiply_sel_result = False):
#     print("")
#     if isPrint: print(f"🟦 Извлекли такие селекторы для поля \"{finding_element}\":")
#     all_selectors = find_text_selector(html, 
#                                        finding_element, 
#                                        return_all_selectors=True, 
#                                        isPriceHandle=is_price, 
#                                        exact=is_exact,
#                                        allow_complex_classes=False)

#     if not all_selectors:
#         if isPrint: print("🟡 Не найдено ни одного подходящего селектора")
#         return ""

#     print(f"Найдено {len(all_selectors)} возможных селекторов")

#     valid_selectors = []

#     # Проверяем каждый селектор
#     for selector in all_selectors:
#         if isPrint: print("")
#         if isPrint: print(f"🟢 Проверка селектора: {selector}")
#         result_text = get_element_from_selector(html, selector)

#         if not result_text:
#             if isPrint: print("❌ Элемент по селектору не найден или текст пуст")
#             continue

#         # Безопасно приводим к строке
#         result_text = str(result_text)

#         # Проверяем наличие подстроки — строгое совпадение по содержанию
#         if finding_element.strip() in result_text.strip():
#             match_score = 1.0
#             if isPrint: print(f"✅ Строгое совпадение: [{result_text[:250]}]")
#         else:
#             # Если нет прямого вхождения — оцениваем схожесть
#             match_score = compute_match_score(result_text, finding_element)
#             if isPrint: print(f"⚪ Совпадение {match_score*100:.1f}%: [{result_text}]")

#         valid_selectors.append({
#             "selector": selector,
#             "result": result_text,
#             "score": match_score
#         })

#     # Если ни один не подошёл
#     if not valid_selectors:
#         if isPrint: print("🔴 Не найдено корректных селекторов")
#         return ""

#     def sort_key(x):
#         selector = x["selector"]
#         score = x["score"]
#         starts_with_id = selector.strip().startswith("#")
#         length = len(selector)
#         # Проверяем, заканчивается ли селектор на атрибут (например, [data-id], [href])
#         ends_with_attr = selector.strip().endswith("]")

#         # Сортируем:
#         # 1️⃣ По убыванию score
#         # 2️⃣ Сначала селекторы, начинающиеся с '#'
#         # 3️⃣ Для '#' — по возрастанию длины, для остальных — по убыванию
#         # 4️⃣ В конце селекторы, у которых в конце есть атрибуты в []
#         return (
#             -score,
#             not starts_with_id,            
#             ends_with_attr,  # False (нет атрибута) < True (есть атрибут)
#             length if starts_with_id else -length,
#         )


#     valid_selectors.sort(key=sort_key)

#     # print("\n🔵 Отсортированные селекторы:")
#     # for i, v in enumerate(valid_selectors, start=1):
#     #     print(f"{i}. {v['selector']} score: {v['score']}")

#     best = valid_selectors[0]
#     if isPrint: print("")
#     if isPrint: print(f"Лучший селектор: {best['selector']} (совпадение {best['score']*100:.1f}%)")

#     # Дистилляция пути
#     # result_distill_selector = distill_selector(html, best["selector"], get_element_from_selector, finding_element)
#     result_distill_selector = simplify_selector_keep_value(html, best["selector"], get_element_from_selector, is_multiply_sel_result)
#     return result_distill_selector



# # region Выбирает один sel

# # Основная функция: Получает css селектор, по текстовому содержанию элемента
# # Эта функция get_css_selector_from_text_value_element получает на вход один элемент
# # Отправляет его в find_text_selector - получает набор css селекторов к этому элементу
# # Проверяет, что каждый селектор действительно верный, и сортирует их по точности совпадения
# # также сортирует по длине, чем короче тем лучше
# # Затем, найденный лучший селектор - дистиллирует
# def get_css_selector_from_text_value_element(html, finding_element, is_price = False, is_exact = True):
#     print("")
#     if isPrint: print(f"🟦 Извлекли такие селекторы для поля \"{finding_element}\":")
#     all_selectors = find_text_selector(html, 
#                                        finding_element, 
#                                        return_all_selectors=True, 
#                                        isPriceHandle=is_price, 
#                                        exact=is_exact,
#                                        allow_complex_classes=False)

#     if not all_selectors:
#         if isPrint: print("🟡 Не найдено ни одного подходящего селектора")
#         return ""

#     print(f"Найдено {len(all_selectors)} возможных селекторов")

#     valid_selectors = []
#     seen_selectors = set()

#     # Проверяем каждый селектор
#     for selector in all_selectors:

#         # Пропускаем дубликаты селектора
#         if selector in seen_selectors:
#             if isPrint: print(f"Пропускаем дубликат селектора: {selector}")
#             continue
        
#         # Сразу метим, что он встречен (даже если потом отфильтруется)
#         seen_selectors.add(selector)

#         if isPrint: print("")
#         if isPrint: print(f"🟢 Проверка селектора: {selector}")
#         result_text = get_element_from_selector(html, selector)

#         if not result_text:
#             if isPrint: print("❌ Элемент по селектору не найден или текст пуст")
#             continue

#         result_text = str(result_text)

#         # Проверяем совпадение текста
#         if finding_element.strip() in result_text.strip():
#             match_score = 1.0
#             if isPrint: print(f"✅ Строгое совпадение: [{result_text[:250]}]")
#         else:
#             match_score = compute_match_score(result_text, finding_element)
#             if isPrint: print(f"⚪ Совпадение {match_score*100:.1f}%: [{result_text}]")

#         # Находим позицию селектора элемента на странице
#         pos = html.find(result_text) if result_text else len(html)
#         pos_norm = pos / len(html)

#         valid_selectors.append({
#             "selector": selector,
#             "result": result_text,
#             "score": match_score,
#             "pos": pos_norm
#         })

#     # Если ни один не подошёл
#     if not valid_selectors:
#         if isPrint: print("🔴 Не найдено корректных селекторов")
#         return ""

#     ######## Не точно рассчитывается позиция pos, и по этому селекторы сортируются неверно

#     def sort_key(x):
#         selector = x["selector"]
#         score = x["score"]
#         pos = x["pos"]
#         starts_with_id = selector.strip().startswith("#")
#         length = len(selector)
#         ends_with_attr = selector.strip().endswith("]")

#         return (
#             -score,       # 1️⃣ По убыванию score
#             pos,          # 2️⃣ По положению в документе (выше = меньше)
#             not starts_with_id,  # 3️⃣ Сначала селекторы с #
#             ends_with_attr,      # 4️⃣ Селекторы с атрибутами в конце
#             length if starts_with_id else -length,  # 5️⃣ Короткие селектоы лучше
#         )

#     valid_selectors.sort(key=sort_key)

#     print("\n🔵 Отсортированные селекторы:")
#     for i, v in enumerate(valid_selectors, start=1):
#         print(f"{i}. {v['selector']} score: {v['score']}, pos: {v['pos']}")

#     best = valid_selectors[0]
#     if isPrint: print("")
#     if isPrint: print(f"Лучший селектор: {best['selector']} (совпадение {best['score']*100:.1f}%)")

#     # Дистилляция пути
#     result_distill_selector = simplify_selector_keep_value(html, best["selector"], get_element_from_selector)
#     return result_distill_selector





def get_css_selector_from_text_value_element(html, finding_element, is_price=False, is_exact=True, is_multiply_sel_result = False):
    print("")
    if not finding_element:
        print("Поле finding_element пусто, пропускаю получение селектора")
        return ""
    if isPrint: print(f"🟦 Извлекли такие селекторы для поля \"{finding_element}\":")
    all_selectors = find_text_selector(html, 
                                       finding_element, 
                                       return_all_selectors=True, 
                                       isPriceHandle=is_price, 
                                       exact=is_exact,
                                       allow_complex_classes=False)

    if not all_selectors:
        if isPrint: print("🟡 Не найдено ни одного подходящего селектора")
        return ""

    print(f"Найдено {len(all_selectors)} возможных селекторов")

    valid_selectors = []
    seen_selectors = set()

    # Проверяем каждый селектор
    for selector in all_selectors:

        # Пропускаем дубликаты селектора
        if selector in seen_selectors:
            # if isPrint: print(f"Пропускаем дубликат селектора: {selector}")
            continue
        
        # Сразу метим, что он встречен (даже если потом отфильтруется)
        seen_selectors.add(selector)

        if isPrint: print("")
        if isPrint: print(f"🟢 Проверка селектора: {selector}")
        result_text = get_element_from_selector(html, selector)

        if not result_text:
            if isPrint: print("❌ Элемент по селектору не найден или текст пуст")
            continue

        result_text = str(result_text)

        # Рассчитываем процентное соотношение
        if not is_exact:
            # Находим, какой процент искомого текста составляет от всего найденного
            finding_len = len(finding_element.strip())
            result_len = len(result_text.strip())
            
            if finding_len == 0:
                percent = 0
            else:
                # Проверяем, содержится ли искомый текст в результате
                if finding_element.strip() in result_text.strip():
                    # Находим максимальное вхождение искомого текста
                    import re
                    matches = re.finditer(re.escape(finding_element.strip()), result_text.strip())
                    max_match_len = max([len(match.group()) for match in matches], default=0)
                    percent = max_match_len / result_len if result_len > 0 else 0
                else:
                    # Если точного вхождения нет, используем коэффициент сходства
                    match_score = compute_match_score(result_text, finding_element)
                    percent = match_score * (finding_len / result_len) if result_len > 0 else 0
        else:
            # Если is_exact = True, устанавливаем фиктивное значение 1
            percent = 1.0

        # Проверяем совпадение текста
        if finding_element.strip() in result_text.strip():
            match_score = 1.0
            if isPrint: print(f"✅ Строгое совпадение: [{result_text[:250]}]{':250' if len(result_text) > 250 else ''}")
        else:
            match_score = compute_match_score(result_text, finding_element)
            if isPrint: print(f"⚪ Совпадение {match_score*100:.1f}%: [{result_text}]")

        # Находим позицию селектора элемента на странице
        pos = html.find(result_text) if result_text else len(html)
        pos_norm = pos / len(html)

        valid_selectors.append({
            "selector": selector,
            "result": result_text,
            "score": match_score,
            "percent": percent,  # Добавляем процентное соотношение
            "pos": pos_norm
        })

    # Если ни один не подошёл
    if not valid_selectors:
        if isPrint: print("🔴 Не найдено корректных селекторов")
        return ""

    def sort_key(x):
        selector = x["selector"]
        score = x["score"]
        percent = x["percent"]  # Процентное соотношение
        pos = x["pos"]
        starts_with_id = selector.strip().startswith("#")
        length = len(selector)
        ends_with_attr = selector.strip().endswith("]")

        return (
            -percent,      # 0️⃣ По убыванию процентного соотношения (основной критерий при is_exact=False)
            -score,       # 1️⃣ По убыванию score
            pos,          # 2️⃣ По положению в документе (выше = меньше)
            not starts_with_id,  # 3️⃣ Сначала селекторы с #
            ends_with_attr,      # 4️⃣ Селекторы с атрибутами в конце
            length if starts_with_id else -length,  # 5️⃣ Короткие селекторы лучше
        )

    valid_selectors.sort(key=sort_key)

    if isPrint:
        print("\n🔵 Отсортированные селекторы:")
        for i, v in enumerate(valid_selectors, start=1):
            print(f"{i}. {v['selector']} score: {v['score']:.2f}, percent: {v['percent']:.2%}, pos: {v['pos']:.4f}")

    best = valid_selectors[0]

    if isPrint: print("")
    if isPrint: print(f"Лучший селектор: {best['selector']} (совпадение {best['score']*100:.1f}%, процент содержания: {best['percent']:.1%})")

    # Дистилляция пути
    result_distill_selector = simplify_selector_keep_value(html, best["selector"], get_element_from_selector, is_multiply_sel_result)
    return result_distill_selector








# region Дистилляция пути
# Дистилляция пути css селектора
# Принимает полный и точный селектор, очищает, и возвращает сокращённый
# удаляя все ненужные звенья
def simplify_selector_keep_value(
    html: str,
    selector: str,
    get_element_from_selector,
    is_multiply_sel_result: bool = False,
):
    """
    Пытается удалить ненужные звенья в селекторе (слева направо).
    Возвращает упрощённый селектор, который гарантированно возвращает
    такое же значение, как исходный селектор, по вызову get_element_from_selector.
    Параметры:
      - html: текст html страницы
      - selector: исходный строгий селектор (через '>')
      - get_element_from_selector: функция (html, selector) -> value (строка)
      - is_multiply_sel_result: True — ориентируемся на количество совпадений,
        False — оставляем старую проверку уникальности (только один результат у селектора)
    """

    def _split_selector_preserving_brackets(selector: str):
        """
        Разбивает селектор по '>' но игнорирует '>' внутри [], (), '' и "".
        Возвращает список звеньев (строк) без лишних пробелов по краям.
        """
        parts = []
        buf = []
        bracket_sq = 0  # []
        bracket_par = 0 # ()
        in_single = False
        in_double = False   

        i = 0
        while i < len(selector):
            ch = selector[i]    

            # переключение состояния строк
            if ch == "'" and not in_double:
                in_single = not in_single
                buf.append(ch)
                i += 1
                continue
            if ch == '"' and not in_single:
                in_double = not in_double
                buf.append(ch)
                i += 1
                continue    

            if not in_single and not in_double:
                if ch == '[':
                    bracket_sq += 1
                    buf.append(ch)
                    i += 1
                    continue
                if ch == ']':
                    if bracket_sq > 0:
                        bracket_sq -= 1
                    buf.append(ch)
                    i += 1
                    continue
                if ch == '(':
                    bracket_par += 1
                    buf.append(ch)
                    i += 1
                    continue
                if ch == ')':
                    if bracket_par > 0:
                        bracket_par -= 1
                    buf.append(ch)
                    i += 1
                    continue    

            # разделитель '>' только если мы не внутри скобок/строк
            if ch == '>' and not in_single and not in_double and bracket_sq == 0 and bracket_par == 0:
                part = ''.join(buf).strip()
                if part != '':
                    parts.append(part)
                buf = []
                # пропускаем возможные пробелы вокруг >
                i += 1
                # skip following spaces
                while i < len(selector) and selector[i].isspace():
                    i += 1
                continue    

            buf.append(ch)
            i += 1  

        last = ''.join(buf).strip()
        if last != '':
            parts.append(last)
        return parts

    # начальная проверка: получаем исходное значение
    try:
        original_value = get_element_from_selector(html, selector)
    except Exception:
        # если исходный селектор уже валидный, но функция кидает — лучше вернуть исходный
        return selector

    # Парсим дерево один раз для оценки уникальности совпадений
    tree = html_lx.fromstring(html)

    # Парсим дерево и фиксируем исходное количество совпадений
    try:
        original_nodes = tree.cssselect(selector)
        original_count = len(original_nodes)
    except Exception:
        original_count = None

    # разбиваем селектор корректно
    parts = _split_selector_preserving_brackets(selector)

    # если один сегмент — возвратим как есть
    if len(parts) <= 1:
        return selector.strip()

    i = 0
    # проходим слева направо. Для каждого индекса пробуем удалить parts[i].
    # Если после удаления результат совпадает с original_value — применяем удаление и
    # остаёмся на том же i (т.к. дальше сдвинулись элементы).
    # Иначе переходим к следующему i.
    while i < len(parts) - 1:
        # нельзя удалить все звенья — должен остаться хотя бы одно
        if len(parts) == 1:
            break

        candidate_parts = parts[:i] + parts[i+1:]
        candidate_selector = " > ".join(candidate_parts)

        # Проверяем количество элементов, которое возвращает кандидат
        try:
            candidate_nodes = tree.cssselect(candidate_selector)
        except Exception:
            candidate_nodes = []

        candidate_value = None
        candidate_match_ok = False

        if is_multiply_sel_result:
            if (
                original_count is not None
                and len(candidate_nodes) == original_count
            ):
                try:
                    candidate_value = get_element_from_selector(
                        html, candidate_selector
                    )
                except Exception:
                    candidate_value = None
                candidate_match_ok = candidate_value == original_value
        else:
            if len(candidate_nodes) == 1:
                try:
                    candidate_value = get_element_from_selector(
                        html, candidate_selector
                    )
                except Exception:
                    candidate_value = None
                candidate_match_ok = candidate_value == original_value

        if candidate_match_ok:
            parts = candidate_parts
            continue
        else:
            # удаление ломает — оставляем звено и идём дальше
            i += 1

    # собрать итоговый селектор
    simplified = " > ".join(parts)
    return simplified

    



# # region Проверка sel
# # Получает и возвращает значение элемента по селектору
# def get_element_from_selector(html, selector, is_ret_len=False):
#     # Проверяем, что селектор не пустой
#     if not selector or not selector.strip():
#         if is_ret_len:
#             return {"result": "", "length_elem": 0}
#         return ""
    
#     tree = html_lx.fromstring(html)
#     search_elem = tree.cssselect(selector)
#     if len(search_elem) == 0:
#         if is_ret_len:
#             return {"result": "", "length_elem": 0}
#         return ""
    
#     element = search_elem[0]

#     # Проверяем, есть ли в селекторе указание атрибута в []
#     attr_match = re.search(r"\[([a-zA-Z0-9_-]+)\]", selector)

#     if attr_match:
#         attr_name = attr_match.group(1)
#         result = element.get(attr_name)
#     else:
#         result = element.text_content().strip()
    
#     if not is_ret_len:
#         return result
#     else:
#         return {"result": result, "length_elem": len(search_elem)}




# region Проверка sel
# Получает и возвращает значение элемента по селектору
def get_element_from_selector(html, selector):
    # Проверяем, что селектор не пустой
    if not selector or not selector.strip():
        return ""
    
    tree = html_lx.fromstring(html)
    search_elem = tree.cssselect(selector)
    if len(search_elem) == 0: 
        # print("🟡 По селектору элемент не найден")
        return ""
    element = search_elem[0]

    # Проверяем, есть ли в селекторе указание атрибута в []
    attr_match = re.search(r"\[([a-zA-Z0-9_-]+)\]", selector)

    if attr_match:
        attr_name = attr_match.group(1)
        result = element.get(attr_name)
    else:
        # Возвращаем только текст внутри элемента
        result = element.text_content().strip()
    
    return result



# Возвращает элемент, и его длину
def get_element_from_selector_and_len(html, selector):
    # Проверяем, что селектор не пустой
    if not selector or not selector.strip():
        return {"result": "", "length_elem": 0}

    tree = html_lx.fromstring(html)
    search_elem = tree.cssselect(selector)
    if len(search_elem) == 0:
        return {"result": "", "length_elem": 0}
    
    element = search_elem[0]

    # Проверяем, есть ли в селекторе указание атрибута в []
    attr_match = re.search(r"\[([a-zA-Z0-9_-]+)\]", selector)

    if attr_match:
        attr_name = attr_match.group(1)
        result = element.get(attr_name)
    else:
        result = element.text_content().strip()
    
    return {"result": result, "length_elem": len(search_elem)}
    # Сделал 2 процедуры, потому что на оригинальную get_element_from_selector завязано очень много всего