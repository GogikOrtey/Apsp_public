"""

"""









from bs4 import BeautifulSoup, Comment, NavigableString

def clean_html_universal(html_content: str) -> str:
    """
    Универсальная очистка HTML для LLM (Black-list подход).
    Удаляет скрипты и стили, но сохраняет структуру, мета-теги и контент.
    Длинные тексты и Base64-изображения обрезаются.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Удаляем ТОЛЬКО явный технический мусор
    # script - исполняемый код
    # style - глобальные стили (забивают контекст)
    # noscript - дублирующий контент
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()

    # 2. Удаляем комментарии (часто содержат старый код)
    for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 3. Обработка SVG
    # Оставляем сам тег SVG (чтобы было видно, что тут иконка), но чистим "кишки"
    for svg in soup.find_all('svg'):
        # Сохраняем атрибуты, но удаляем вложенные path, circle и т.д.
        svg.clear() 
        # Можно добавить пометку, что контент удален
        svg.append(NavigableString(""))

    # 4. Обработка атрибутов (Base64 и события)
    for tag in soup.find_all(True):
        attrs_to_modify = {}
        for attr, value in tag.attrs.items():
            # А. Удаляем JS-события (onclick, onmouseover...)
            if attr.lower().startswith('on'):
                attrs_to_modify[attr] = None # Пометить на удаление
                continue

            # Б. Проверка на Base64 (картинки, зашитые в код)
            # Если значение атрибута - строка и начинается с data:image
            if isinstance(value, str) and value.startswith('data:'):
                if len(value) > 50: # Если это не коротенький пиксель
                    attrs_to_modify[attr] = "<--BASE64_DATA_TRUNCATED-->"
            
            # В. (Опционально) Можно обрезать супер-длинные ссылки, если они не data:
            # Но лучше оставить, вдруг это важная ссылка на товар

        # Применяем изменения атрибутов
        for attr, val in attrs_to_modify.items():
            if val is None:
                del tag.attrs[attr]
            else:
                tag.attrs[attr] = val

    # 5. Умное обрезание длинного текста (Truncate)
    # Проходимся по всем текстовым узлам
    for text_node in soup.find_all(text=True):
        # Игнорируем пробельные узлы
        if not text_node.strip():
            continue
        
        # Если текст слишком длинный (например, статья или описание)
        if len(text_node) > 250:
            # Оставляем 200 символов сначала и 50 с конца
            head = text_node[:200]
            tail = text_node[-50:]
            # Заменяем содержимое узла
            new_text = f"{head} ... <--TRUNCATED_TEXT--> ... {tail}"
            text_node.replace_with(new_text)

    # 6. Финальная сборка
    # separator='\n' добавляет переносы строк, чтобы HTML не слипся в кашу
    return soup.prettify()