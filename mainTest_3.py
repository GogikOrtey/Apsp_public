# # Подключение всех библиотек
# from import_all_libraries import * 

# now = int(time.time())
# print(now)

# Собирает название парсера из хоста
def set_parser_name(host):
    # Как нужно чистим домен
    parser_file_name = host.split("://")[1].split("/")[0]
    parser_file_name = parser_file_name.replace("www.", "")
    parser_file_name = parser_file_name.replace(".", "").replace("-", "")
    # TODO регионы потом удалять, но это сильно позже

    base_name_part = "JS_Base_" + parser_file_name
    print("Имя парсера: " + base_name_part)

    return base_name_part

host = "https://makitaclub.ru"
set_parser_name(host)