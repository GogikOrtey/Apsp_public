# Получает css путь к элементу, используя YandexGPT
def handle_css_selector_uce_YandexGPT():
    ### Выделил в функцию, но не проверил что работает
    substring = "Makita"
    found = find_contexts(html, substring)
    # for i, ctx in enumerate(found, 1):
    #     print(f"\n=== Фрагмент {i} ===")
    #     print(ctx)

    # print(found[0])

    ### Запрос отлажен  
    prompt = f"""
    Отправляю тебе фрагмент html кода. Конкретно из этого примера мы извлекаем значение "{substring}", 
    но тебе нужно найти пример, что бы он работал и с другими значениями. 
    В ответе напиши только один путь селекторов, по которому можно извлечь такое значение из html страницы.
    {found[0]}
    """

    print("_____________________________________")
    print("Посылаем запрос")
    print(prompt)

    # response = sendMessageToYandexGPT(prompt)

