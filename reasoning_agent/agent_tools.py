# Здесь будут описания инструментов для агента

import json

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




# region Декоратор анннотаций

TOOLS = {} # Описания будут собираться в этот словарь

def tool(name, description, args=None, returns=None, example_args=None):
    """Декоратор для регистрации инструмента с аннотацией"""
    def decorator(func):
        TOOLS[name] = {
            "func": func,
            "name": name,
            "description": description,
            "args": args or [],
            "returns": returns,
            "example_args": example_args or {}
        }
        return func
    return decorator


# region Реализация инструментов с аннотациями

@tool(
    name="list_files",
    description="Возвращает список всех файлов в окружении",
    args=[],
    # ВАЖНО: лучше хранить `returns` как структуру (dict/list), а не как JSON-строку внутри строки.
    # Тогда при json.dumps() не будет экранирования кавычек вида \"...\".
    returns={
        "files": ["notes.txt", "todo.txt", "..."]
    },
    example_args={}
)
def list_files():
    # JSON-friendly ответ, чтобы совпадало с аннотацией returns
    return {"files": list(FILES.keys())}


@tool(
    name="read_file",
    description="Читает содержимое файла по имени. Возвращает словарь с содержимым и статусом",
    args=[
            {
                "name": "filename", 
                "type": "str", 
                "required": True, 
                "description": "Имя файла"
            }
        ],
    returns=[
        {"status": "ok", "content": "..."},
        {"status": "error", "content": None}
    ],
    example_args={"filename": "todo.txt"}
)
def read_file(filename):
    if filename in FILES:
        return {"status": "ok", "content": FILES[filename]}
    else:
        return {"status": "error", "content": None}


@tool(
    name="search_in_file",
    description="Ищет вхождения подстроки в тексте файла",
    args=[
        {
            "name": "filename",
            "type": "str", 
            "required": True, 
            "description": "Имя файла"
        },
        {
            "name": "substr", 
            "type": "str", 
            "required": True, 
            "description": "Подстрока для поиска"
        }
    ],
    returns={
        "status": "ok|error",
        "count": "int",
        "first_index": "int|null"
    },
    example_args={"filename": "todo.txt", "substr": "презентац"}
)
def search_in_file(filename, substr):
    if filename not in FILES:
        return {"status": "error", "count": 0, "first_index": None}
    
    text = FILES[filename]
    count = text.count(substr)
    first_index = text.find(substr) if count > 0 else None
    
    return {"status": "ok", "count": count, "first_index": first_index}






# region Возврат аннотаций
def get_tools_annotations(as_json: bool = True):
    """
    Возвращает аннотации всех инструментов (без самих функций).

    as_json=True  -> вернуть красивую JSON-строку (удобно печатать/логировать)
    as_json=False -> вернуть Python-dict (удобно смотреть в дебаггере без экранирования)
    """
    annotations = {}
    for name, data in TOOLS.items():
        annotations[name] = {
            "name": data["name"],
            "description": data["description"],
            "args": data["args"],
            "returns": data["returns"],
            "example_args": data["example_args"]
        }
    
    if not as_json:
        return annotations
    return json.dumps(annotations, ensure_ascii=False, indent=4) # в текстовом виде



