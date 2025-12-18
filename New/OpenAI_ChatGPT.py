#region Импорты и инициализация

# Вынесенные отдельно функции
from addedFunc import *
# Подключение всех библиотек
from import_all_libraries import * 

# Чтобы при запуске файла из папки New/ были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Заружаем ключ OpenAI и инициализируем клиент
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY")
if not api_key:
    raise RuntimeError(
        "OpenAI API key not found. Add OPEN_AI_API_KEY to your .env file"
    )

client = OpenAI(
    api_key=api_key
)



#region Доп. функции

# # Получить все доступные модели
# models = client.models.list()

# for m in models.data:
#     print(m.id)




"""

Для размышлений и построения плана: o3
Универсальный агент: gpt-5.2
Для работы с кодом: gpt-5.1-codex-max
Для парсинга и анализа: gpt-5.2

Человечная и дружелюбная: gpt-4o

"""




# Системные роли:
"""

Ты опытный Python-разработчик
Ты reasoning-агент: разбивай задачи на шаги, проверяй промежуточные результаты и выдавай план действий.
Ты утка. Крякай на каждый вопрос

Задаётся как:
"input": [
    {
        "role": "system",
        "content": "Ты опытный Python-разработчик"
    },
    ...

"""




#region Основные функции

# Простой вариант использования API
def sendMessageToChatGPT_simple(prompt: str, is_print = True, model = "gpt-5.2"):
    if is_print:
        print(f"\n💫Запрос к ChatGPT, модель {model}\nPROMPT:\n{prompt}\n")

    start = time.time()
    response = client.responses.create(
        model=model,
        input=prompt
    )

    if is_print:
        print(f'\n💬 AI ANSWER:\n"{response.output_text}"\n')
        emit_execution_time(start, emit=print)

    return response.output_text
    # print(response.output_text)


# result_request = sendMessageToChatGPT_simple(prompt = "Какой сейчас год?", is_print = True)
# sendMessageToChatGPT_for_history("Сколько будет 2+2?", model="gpt-4o")








## Только обавил температуру, перед добавлением истории
# # Запросы с историей разговора
# def sendMessageToChatGPT_for_history(prompt: str, is_print = True, model = "gpt-5.2", temperature = None):
#     if is_print:
#         print(f"\n💫Запрос к ChatGPT с историей, модель {model}\nPROMPT:\n{prompt}\n")

#     start = time.time()
#     params = {
#         "model": model,
#         "input": [
#             {
#                 "role": "system",
#                 "content": "Ты опытный Python-разработчик"
#             },
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ]
#     }
#     if temperature is not None:
#         params["temperature"] = temperature

#     response = client.responses.create(**params)

#     if is_print:
#         print(f'\n💬 AI ANSWER:\n"{response.output_text}"\n')
#         emit_execution_time(start, emit=print)

#     return response.output_text











# Запросы с историей разговора
def sendMessageToChatGPT_for_history(
        prompt: str,        # Запрос к нейросети
        is_print = True,    # Печатать ли запрос и ответ в консоли
        model = "gpt-5.2",  # Используемая модель
        temperature = None  # Задание температуры ответа [от 0 до 1.0]
    ):
    if is_print:
        print(f"\n💫Запрос к ChatGPT с историей, модель {model}\nPROMPT:\n{prompt}\n")

    start = time.time()
    params = {
        "model": model,
        "input": [
            # {
            #     "role": "system",
            #     "content": "Ты опытный Python-разработчик"
            # },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    if temperature is not None:
        params["temperature"] = temperature

    response = client.responses.create(**params)

    if is_print:
        print(f'\n💬 AI ANSWER:\n"{response.output_text}"\n')
        emit_execution_time(start, emit=print)

    return response.output_text






#region Использование





# result_request = sendMessageToChatGPT_for_history("Какая самая высокая гора на земле?")
# result_request = sendMessageToChatGPT_for_history("Когда люди впервые открыли эту гору?")


