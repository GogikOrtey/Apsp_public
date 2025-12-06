
# Вынесенные отдельно функции
from addedFunc import *
from gen_data_input_table import data_input_table # Входные данные
from extracting_selector_from_html import *

# region Сохранение кеша

CACHE_FILE = "cache.json"
MAX_AGE_HOURS = 18

# Инициализация глобального кеша при загрузке модуля
global_cache = {}

def load_cache(file=CACHE_FILE):
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"simple": []}

# Инициализируем глобальный кеш при загрузке модуля
global_cache = load_cache()

# Получаем html из кеша для ссылки (работает с глобальным кешем)
def get_html_from_cache(link, return_metadata=False):
    """
    Получает HTML для ссылки из глобального кеша.
    Если страницы нет в кеше или она устарела - загружает заново и обновляет кеш.
    
    Args:
        link: URL страницы
        return_metadata: Если True, возвращает кортеж (html, data_time_str, timestamp_int),
                        иначе возвращает только HTML-контент
    
    Returns:
        str: HTML-контент (если return_metadata=False)
        tuple: (html, data_time_str, timestamp_int) (если return_metadata=True)
    """
    now = int(time.time())
    # Ищем страницу в кеше
    for item in global_cache["simple"]:
        if item["link"] == link:
            age_hours = (now - item["timestamp"]) / 3600
            if age_hours <= MAX_AGE_HOURS:
                print(f"📤 Берем страницу из кеша: {link} (возраст {age_hours:.2f} ч.)")
                if return_metadata:
                    return item["html_content"], item["data_time"], item["timestamp"]
                return item["html_content"]
            break  # страница есть, но устарела — выйдем и загрузим заново

    # Если страницы нет в кеше или она старая — получаем заново
    html = get_html(link) 
    data_time_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    timestamp_int = int(time.time())

    # Обновляем или добавляем в глобальный кеш
    updated = False
    for item in global_cache["simple"]:
        if item["link"] == link:
            item.update({
                "html_content": html,
                "data_time": data_time_str,
                "timestamp": timestamp_int
            })
            updated = True
            break
    if not updated:
        global_cache["simple"].append({
            "link": link,
            "html_content": html,
            "data_time": data_time_str,
            "timestamp": timestamp_int
        })

    if return_metadata:
        return html, data_time_str, timestamp_int
    if return_metadata:
        return html, data_time_str, timestamp_int
    return html

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
    
    # Обновляем глобальный кеш после сохранения
    global global_cache
    global_cache = updated_cache


