# Здесь будут описания инструментов для агента


"""

Начальные инструменты:

list_files - возвращает список файлов в окружении
read_file - читает содержимое файла по имени
search_in_file - ищет вхождения подстроки в тексте файла

"""


# Пример входных данных

FILES = {
    "notes.txt": "Встреча в пятницу. Купить хлеб. Проверить отчёт.",
    "todo.txt": "Срочно: отправить письмо Алексею. Подготовить презентацию.",
    "archive.txt": "Старые заметки за 2022 год."
}

# region Реализация инструментов

# region Реализация инструментов

def list_files():
    """Возвращает список всех файлов в окружении"""
    return list(FILES.keys())


def read_file(filename):
    """Читает содержимое файла по имени. Возвращает словарь с содержимым и статусом"""
    if filename in FILES:
        return {"status": "ok", "content": FILES[filename]}
    else:
        return {"status": "error", "content": None}


def search_in_file(filename, substr):
    """
    Ищет вхождения подстроки в тексте файла.
    Возвращает словарь:
      - count: количество найденных совпадений
      - first_index: индекс первого совпадения (или None, если не найдено)
      - status: ok/error
    """
    if filename not in FILES:
        return {"status": "error", "count": 0, "first_index": None}
    
    text = FILES[filename]
    count = text.count(substr)
    first_index = text.find(substr) if count > 0 else None
    
    return {"status": "ok", "count": count, "first_index": first_index}