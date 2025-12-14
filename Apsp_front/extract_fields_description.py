import re
import os
import hashlib
import json

def calculate_file_hash(file_path):
    """
    Вычисляет SHA256 хеш содержимого файла.
    
    Args:
        file_path: путь к файлу
        
    Returns:
        str: hex-представление хеша
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_fields_from_content(content):
    """
    Извлекает поля из содержимого файла.
    
    Args:
        content: содержимое файла (строка)
        
    Returns:
        dict: словарь с полями в формате {"name": "Наименование товара", ...}
    """
    fields_dict = {}
    
    # Удаляем многострочные комментарии перед обработкой
    # Удаляем многострочные комментарии /** ... */
    content = re.sub(r'/\*\*.*?\*/', '', content, flags=re.DOTALL)
    # Удаляем однострочные комментарии /* ... */
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    # Обрабатываем каждую строку
    for line in content.split('\n'):
        # Удаляем пробелы в начале и конце
        line = line.strip()
        
        # Пропускаем пустые строки
        if not line:
            continue
        
        # Пропускаем строки, которые закомментированы (начинаются с //)
        if line.startswith('//'):
            continue
        
        # Ищем паттерн: export const name: field = ['name', 'description'];
        # Паттерн поддерживает как одинарные, так и двойные кавычки
        pattern = r'export\s+const\s+(\w+)\s*:\s*field\s*=\s*\[["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']\s*\];?'
        
        match = re.search(pattern, line)
        if match:
            var_name = match.group(1)  # имя переменной (например, 'name')
            # первый элемент массива (например, 'name')
            first_element = match.group(2)
            description = match.group(3)  # описание (например, 'Наименование товара')
            
            # Используем имя переменной как ключ, описание как значение
            fields_dict[var_name] = description
    
    return fields_dict


def extract_fields_description(file_path='add_files/Fields_static.ts', json_path='fields_descriptions.json'):
    """
    Извлекает из файла Fields_static.ts все незакомментированные строки,
    а затем добавляет каждый элемент в словарь, преобразуя структуру
    export const name: field = ['name', 'Наименование товара'];
    в "name": "Наименование товара"
    
    Использует кеширование: если хеш файла не изменился, возвращает данные из JSON.
    
    Args:
        file_path: путь к файлу Fields_static.ts
        json_path: путь к файлу с кешем (fields_descriptions.json)
        
    Returns:
        dict: словарь с полями в формате {"name": "Наименование товара", ...}
    """
    # Проверяем существование исходного файла
    if not os.path.exists(file_path):
        print(f"Файл {file_path} не найден")
        return {}
    
    # Вычисляем хеш исходного файла
    current_hash = calculate_file_hash(file_path)
    
    # Проверяем существование JSON файла с кешем
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Если структура правильная и хеш совпадает, возвращаем кешированные данные
            if isinstance(cache_data, dict) and 'hash' in cache_data and 'fields' in cache_data:
                if cache_data['hash'] == current_hash:
                    print(f"Используется кеш из {json_path} (хеш совпадает)")
                    return cache_data['fields']
                else:
                    print(f"Хеш изменился, пересоздаём {json_path}")
            else:
                print(f"Некорректная структура кеша, пересоздаём {json_path}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Ошибка при чтении кеша: {e}, пересоздаём {json_path}")
    
    # Читаем файл и извлекаем поля
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    fields_dict = extract_fields_from_content(content)
    
    # Добавляем дополнительные поля в конец
    fields_dict["InStock_trigger"] = "Триггер наличия товара"
    fields_dict["OutOfStock_trigger"] = "Триггер отсутствия товара"
    
    # Сохраняем результат в JSON с хешем
    cache_data = {
        'hash': current_hash,
        'fields': fields_dict
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2, sort_keys=False)
    
    print(f"Результат сохранен в {json_path} (новый хеш)")
    
    return fields_dict


if __name__ == "__main__":
    # Пример использования
    result = extract_fields_description()
    print(f"\nВсего извлечено полей: {len(result)}")
    print("\nИзвлеченные поля:")
    for key, value in result.items():
        print(f'  "{key}": "{value}"')




#####
# Поле link надо ставить в самое начало