# Подключение всех библиотек
from import_all_libraries import * 

# TODO: Когда здесь наберётся достаточно функций, разбить их по категориям, и добавить оглавление


def clearAnswerCode(input_code):
    return input_code

# def clean_html_text(s: str, keep_tags=False) -> str:
#     if not isinstance(s, str):
#         return ""

#     # 1️⃣ Декодируем HTML-сущности (&nbsp; → пробел, &amp; → &)
#     s = html_lx.unescape(s)

#     # 2️⃣ Убираем управляющие символы (0–31, кроме \n и \t)
#     s = re.sub(r'[\x00-\x09\x0B-\x1F\x7F]', '', s)

#     # 3️⃣ (опционально) удаляем HTML-теги
#     if not keep_tags:
#         s = re.sub(r'<[^>]+>', '', s)

#     # 4️⃣ Убираем невидимые пробелы, в т.ч. неразрывные
#     s = s.replace('\xa0', ' ').replace('\u200b', ' ')  # nbsp и zero-width space

#     # 5️⃣ Заменяем все виды пробелов и переносов на одиночный пробел
#     s = re.sub(r'\s+', ' ', s)

#     # 6️⃣ Убираем лишние пробелы по краям
#     s = s.strip()

#     return s

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
    

class ErrorHandler(Exception):
    """Моё кастомное исключение."""

    def __init__(self, message, error_code=0):
        self.message = message
        self.error_code = error_code

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


# Транслированная функция format_price 
def format_price(value: str, separator: str = ".") -> str:
    # Удаляем все символы, кроме цифр и разделителя
    cleaned = re.sub(rf"[^0-9{re.escape(separator)}]+", "", value)

    # Заменяем разделитель на точку
    cleaned = cleaned.replace(separator, ".")

    # Ищем число с максимум 2 знаками после точки
    match = re.search(r"\d+(?:\.\d{0,2})?", cleaned)

    return match.group(0) if match else ""