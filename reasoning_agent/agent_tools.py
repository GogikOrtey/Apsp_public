# Здесь будут описания инструментов для агента


"""

Начальные инструменты:

list_files - возвращает список файлов в окружении
read_file - читает содержимое файла по имени
search_in_file - ищет вхождения подстроки в тексте файла

"""





# region Описание для каждогго инструмента

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
    returns='JSON: {"files": ["notes.txt", "todo.txt", ...]}',
    example_args={}
)
def list_files():
    return list(FILES.keys())


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
    returns='JSON: {"status":"ok","content":"..."} или {"status":"error","content":None}',
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
    returns='JSON: {"status":"ok/error", "count":int, "first_index":int or None}',
    example_args={"filename": "todo.txt", "substr": "презентац"}
)
def search_in_file(filename, substr):
    if filename not in FILES:
        return {"status": "error", "count": 0, "first_index": None}
    
    text = FILES[filename]
    count = text.count(substr)
    first_index = text.find(substr) if count > 0 else None
    
    return {"status": "ok", "count": count, "first_index": first_index}
