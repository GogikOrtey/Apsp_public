# Подключение всех библиотек
from import_all_libraries import * 

from gen_data_input_table import data_input_table

# TODO: Когда здесь наберётся достаточно функций, разбить их по категориям, и добавить оглавление

# region print_json
def print_json(input_json):
    text = json.dumps(input_json, indent=4, ensure_ascii=False)
    text = text.replace('\\"', '"')
    print(text)

# region timing
def emit_execution_time(start: float, emit: Callable[[str], None] = print) -> float:
    """
    Печатает/эмитит время выполнения в стиле global_code.py (секунды/минуты).

    :param start: timestamp, полученный из time.time()
    :param emit: функция-эмиттер (например, print или кастомный emit для логов)
    :return: elapsed (секунды)
    """
    elapsed = time.time() - start
    emit("")
    if elapsed < 60:
        emit(f"🕚 Время выполнения: {elapsed:.2f} секунд")
    else:
        emit(f"🕚 Время выполнения: {elapsed / 60:.1f} минут")
    return elapsed

# region get_current_date
# Возвращает текущую дату в формате "4 дек 2025"
def get_current_date():
    # Получаем текущую дату
    today = date.today()
    
    # Словарь русских названий месяцев (аббревиатуры)
    russian_months = {
        1: "Янв", 2: "Фев", 3: "Мар", 4: "Апр",
        5: "Май", 6: "Июн", 7: "Июл", 8: "Авг",
        9: "Сен", 10: "Окт", 11: "Ноя", 12: "Дек"
    }
    
    # Форматируем: день месяц_аббревиатура год
    day = today.day
    month_abbr = russian_months[today.month]
    year = today.year
    formatted_date = f"{day} {month_abbr} {year}"  # Например: 4 дек 2025

    return formatted_date

    
def normalize_image_url(s: str) -> str:
    # убираем домен и протокол
    s = re.sub(r'^https?://[^/]+', '', s)
    return s

def similarity_percent_smart(a: str, b: str) -> float:
    a_n = normalize_image_url(a)
    b_n = normalize_image_url(b)
    return SequenceMatcher(None, a_n, b_n).ratio() * 100


def clearAnswerCode(input_code):
    return input_code

# region get_html
def get_html(url: str, headers: dict = None, timeout: int = 10, is_clear_html = True) -> str:
    """
    Отправляет GET-запрос на указанный URL и возвращает HTML-ответ.

    :param url: Ссылка на сайт
    :param headers: Словарь с заголовками (по умолчанию None)
    :param timeout: Время ожидания ответа сервера (секунды)
    :return: HTML-строка
    """
    if headers is None:
        # Некоторые сайты требуют User-Agent
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()  # Проверяем статус ответа (200 OK)
        if is_clear_html == False: return response.text
        cleared_text = clean_html_preserve_structure(response.text)
        return cleared_text
    except requests.RequestException as e:
        print(f"Ошибка при запросе к {url}: {e}")
        return ""
    

# region ErrorHandler
class ErrorHandler(Exception):
    """Моё кастомное исключение."""

    def __init__(self, message, error_code=0):
        self.message = message
        self.error_code = error_code

        message_global.append({"1": f"🔴 Агент завершил работу с ошибкой: {message}"})



        full_msg = (
            f"🔴 Агент завершил работу с ошибкой: {message}"
            if error_code == 0
            else f"🔴 Агент завершил работу с ошибкой: {message}. Стадия и шаг: {error_code}"
        )
        super().__init__(full_msg)


# Примеры использования:
# raise ErrorHandler("Кастомное исключение")           # без кода
# raise ErrorHandler("Кастомное исключение", 1)      # с числовым кодом
# raise ErrorHandler("Кастомное исключение", "2-1")    # с текстовым кодом



# region find_contexts
# Находит и возвращает все фрагменты подстроки в html
# Сейчас используется только для тестов
# Но писалось для извлечения малого контектса для YandexGPT
def find_contexts(text: str, substring: str, context_size: int = 300) -> list[str]:
    """
    Находит все вхождения `substring` в `text` и возвращает список
    контекстов (по `context_size` символов до и после совпадения).
    Если контексты перекрываются — объединяет их.
    """
    results = []
    substring = re.escape(substring)  # экранируем спецсимволы
    matches = list(re.finditer(substring, text, flags=re.IGNORECASE))

    for match in matches:
        start = max(0, match.start() - context_size)
        end = min(len(text), match.end() + context_size)

        # Проверяем, не пересекается ли с уже добавленным результатом
        if results and start <= results[-1][1]:
            # объединяем с предыдущим фрагментом
            prev_start, prev_end = results[-1]
            results[-1] = (prev_start, max(prev_end, end))
        else:
            results.append((start, end))

    # формируем итоговые куски текста
    contexts = [text[s:e] for s, e in results]
    return contexts


# # Получаем куски по подстроке
# result = find_contexts(html, substring_name)
# print(result)




# region clean_html_preserve_structure
### Очистка html ответа
def clean_html_preserve_structure(html_text: str) -> str:
    """
    Чистит ТОЛЬКО текстовые узлы в html_text:
    - декодирует html-сущности внутри текстов,
    - удаляет управляющие символы и zero-width,
    - заменяет множественные пробелы на один.
    Теги/атрибуты/скрипты не меняются.
    """

    # Регулярка для удаления управляющих символов (кроме таб, LF, CR если нужно)
    _CTRLS_RE = re.compile(r'[\x00-\x09\x0B-\x1F\x7F]')

    # теги, содержимое которых не трогаем
    _SKIP_TAGS = {"script", "style", "noscript"}

    def _clean_text_node(s: str) -> str:
        if s is None:
            return s
        # 1) декодируем HTML-сущности только в текстовой ноде
        s = std_html.unescape(s)
        # 2) убираем управляющие / невидимые символы
        s = _CTRLS_RE.sub("", s)
        # 3) заменяем zero-width и non-breaking на обычный пробел
        s = s.replace('\u200b', ' ').replace('\u00a0', ' ')
        # 4) сводим подряд идущие пробелы/тр/таб/переносы в один пробел
        s = re.sub(r'\s+', ' ', s)
        # 5) аккуратно убираем пробелы по краям
        return s.strip()

    if not isinstance(html_text, str):
        return ""

    # Сохраним признак doctype в начале (если есть), чтобы вернуть его при сериализации
    doctype_prefix = ""
    stripped = html_text.lstrip()
    if stripped.lower().startswith("<!doctype"):
        # берем первую строку до '>' как doctype
        i = html_text.lower().find('>')
        if i != -1:
            doctype_prefix = html_text[:i+1]
            # оставим тело без doctype для парсера (парсер тоже умеет с ним, но на всякий)
            html_body = html_text[i+1:]
        else:
            html_body = html_text
    else:
        html_body = html_text

    # Парсим документ (document_fromstring сохраняет корень <html>)
    try:
        doc = lh.document_fromstring(html_body)
    except etree.ParserError:
        # на случай кривого HTML — используем более мягкий парсер
        parser = lh.HTMLParser(recover=True)
        doc = lh.fromstring(html_body, parser=parser)

    # Проходим по всем элементам и чистим .text и .tail, пропуская _SKIP_TAGS
    for el in doc.iter():
        # пропускаем комментарии
        if isinstance(el, etree._Comment):
            continue

        tag = getattr(el, "tag", None)
        if isinstance(tag, str) and tag.lower() in _SKIP_TAGS:
            # не трогаем содержание script/style
            continue

        # очистка основного текста внутри тега
        if el.text:
            cleaned = _clean_text_node(el.text)
            # если текст стал пустым — устанавливаем None (чтобы не писать "")
            el.text = cleaned if cleaned != "" else None

        # очистка хвостового текста (после тега, перед следующ. sibling)
        if el.tail:
            cleaned_tail = _clean_text_node(el.tail)
            el.tail = cleaned_tail if cleaned_tail != "" else None

    # Сериализуем назад в HTML
    out_html = lh.tostring(doc, encoding='unicode', method='html', pretty_print=False)

    # если был doctype — вернём его спереди (без дублирования)
    if doctype_prefix:
        # убрать возможный ведущий пробел/новую строку
        out_html = doctype_prefix + "\n" + out_html.lstrip()

    return out_html


# region format_price
# Транслированная функция format_price 
def format_price(value: str, separator: str = ".") -> str:
    # Удаляем все символы, кроме цифр и разделителя
    cleaned = re.sub(rf"[^0-9{re.escape(separator)}]+", "", value)

    # Заменяем разделитель на точку
    cleaned = cleaned.replace(separator, ".")

    # Ищем число с максимум 2 знаками после точки
    match = re.search(r"\d+(?:\.\d{0,2})?", cleaned)

    return match.group(0) if match else ""
    

# region clean_selector_from_double_hyphen
# Удаляет все названия классов, начинающиеся с .-- 
# т.к. это ломает дальнейшую логику извлечения элементов из селекторов
def clean_selector_from_double_hyphen(selector_str):
    if not selector_str:
        return selector_str
    
    # Регулярное выражение ищет:
    # \.       -> точку
    # --       -> два дефиса сразу после точки
    # [\w-]+   -> любые буквы, цифры, подчеркивания или дефисы (имя класса)
    pattern = r'\.--[\w-]+'
    
    # Заменяем все найденные вхождения на пустую строку
    cleaned_selector = re.sub(pattern, '', selector_str)
    
    # Удаляем возможные двойные пробелы, которые могли остаться после удаления классов
    cleaned_selector = re.sub(r'\s+', ' ', cleaned_selector).strip()
    
    return cleaned_selector


# region compute_match_score_2
# # Вспомогательная функция для оценки схожести
# def compute_match_score(found_text, target_text):
#     """Оценка схожести строк по количеству совпадающих символов"""
#     found_text = found_text.strip().lower()
#     target_text = target_text.strip().lower()

#     if not found_text or not target_text:
#         return 0.0

#     # Длина совпадающих символов (по порядку)
#     common = sum(1 for a, b in zip(found_text, target_text) if a == b)
#     score = common / max(len(target_text), len(found_text))
#     return score

# Сравнение перестановками. Сравнивает строки более точно
def compute_match_score_2(found_text, target_text):
    found_text = found_text.strip().lower()
    target_text = target_text.strip().lower()

    if not found_text or not target_text:
        return 0.0

    return SequenceMatcher(None, found_text, target_text).ratio()



# region Check html
# # Проверяю, что html-страница доступна, и данные первого товара на ней есть
# def check_avialible_html():
#     # TODO: Потом добавить обработку, что бы он искал не полным сравнением подстроки названия товара при проверке, а частичным
#     # Это когда напишу такую штуку для price

#     first_item_link = data_input_table["links"]["simple"][0]["link"]
#     html = get_html(first_item_link)

#     text_includes = data_input_table["links"]["simple"][0]["name"] 
#     if not text_includes in html:
#         print("🟠 Подстрока не найдена.")
#         raise ErrorHandler("При открытии страницы 1 товара, на ней не было обнаружено названия товара")



# # region check_avialible_html
# # Проверяю, что название первого товара содержится в html первой ссылки
# # Это проверка на то, есть ли на сайте какая-то защита, типо куратора
# def check_avialible_html():
#     # 1. Данные
#     first_item_link = data_input_table["links"]["simple"][0]["link"]
#     target_name = data_input_table["links"]["simple"][0]["name"].strip().lower()
    
#     # Получаем HTML
#     html_content = get_html(first_item_link).lower()
    
#     # 2. Быстрая очистка HTML от тегов (оставляем только текст)
#     # Это важно, чтобы название не "разбилось" тегами типа <b>Name</b>
#     text_content = re.sub(r'<[^>]+>', ' ', html_content)
#     # Убираем лишние пробелы (превращаем "  " в " ")
#     text_content = " ".join(text_content.split())

#     # 3. Магия difflib: ищем самый длинный общий кусок
#     # SequenceMatcher(isjunk, string_A, string_B)
#     matcher = SequenceMatcher(None, target_name, text_content)
    
#     # Ищем совпадение в границах всей длины строк
#     match = matcher.find_longest_match(0, len(target_name), 0, len(text_content))
    
#     # match.size — это длина совпавшего куска
#     # Считаем процент: (длина совпадения) / (длина искомого названия)
#     similarity = match.size / len(target_name)

#     # 4. Проверка
#     threshold = 0.8 # 80%
    
#     if similarity < threshold:
#         print(f"🟠 Частичное совпадение слишком слабое: {similarity:.2%}")
#         print(f"Искали: {target_name}")
#         # Показываем, что именно нашлось (срез текста по найденным индексам)
#         found_part = text_content[match.b : match.b + match.size]
#         print(f"Нашли кусок: '{found_part}'")
        
#         raise ErrorHandler("Название товара не найдено на странице (даже частично).")        
    # print(f"🟢 Товар найден! Совпадение: {similarity:.2%}")






# region check_avialible_html
# Проверяю, что название первого товара содержится в html первой ссылки
# Это проверка на то, есть ли на сайте какая-то защита, типо куратора
def check_avialible_html():
    # 1. Данные
    first_item_link = data_input_table["links"]["simple"][0]["link"]
    target_name = data_input_table["links"]["simple"][0]["name"].strip().lower()
    
    # Получаем HTML
    html_content = get_html(first_item_link).lower()
    
    # 2. Быстрая очистка HTML от тегов (оставляем только текст)
    # Это важно, чтобы название не "разбилось" тегами типа <b>Name</b>
    text_content = re.sub(r'<[^>]+>', ' ', html_content)
    # Убираем лишние пробелы (превращаем "  " в " ")
    text_content = " ".join(text_content.split())

    # 3. Магия difflib: ищем самый длинный общий кусок
    matcher = SequenceMatcher(None, target_name, text_content)
    match = matcher.find_longest_match(0, len(target_name), 0, len(text_content))
    
    similarity = match.size / len(target_name)

    # 4. Проверка
    threshold = 0.8  # 80%
    
    if similarity < threshold:
        # Если не совпало частичным, то пробуем простым включением
        # (старая логика)
        first_item_link = data_input_table["links"]["simple"][0]["link"]
        html = get_html(first_item_link)

        text_includes = data_input_table["links"]["simple"][0]["name"] 
        if text_includes in html:
            return

        # Если всё таки нет вхождений

        print(f"🟠 Частичное совпадение слишком слабое: {similarity:.2%}")
        print(f"Искали: {target_name}")
        found_part = text_content[match.b : match.b + match.size]
        print(f"Нашли кусок: '{found_part}'")

        # Сохраняем HTML перед ошибкой
        try:
            with open("current_html.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print("HTML сохранён в current_html.html")
        except Exception as save_err:
            print(f"Ошибка сохранения HTML: {save_err}")

        raise ErrorHandler("Название товара не найдено на странице (даже частично).")
