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


# Системные промпты
# (Без них модель может вести себя нестабильно, часто меняя стили общения)
"""
Рекомендуемый нейтральный

You are a helpful, accurate, and concise AI assistant.
Follow the user's instructions carefully.
If something is unclear or missing, ask for clarification.
Do not make up facts.

Вы - полезный, точный и лаконичный ИИ-помощник.
Внимательно следуйте инструкциям пользователя.
Если что-то непонятно или чего-то не хватает, попросите разъяснений.
Не придумывайте факты.




Версия для разработки

You are a precise and reliable AI assistant.
Provide clear, structured, and technically correct answers.
If you are unsure, say so explicitly.
Do not invent details or assumptions.

Вы - точный и надёжный ИИ-помощник.
Давайте чёткие, структурированные и технически правильные ответы.
Если вы не уверены, скажите об этом прямо.
Не придумывайте детали или предположения.




Нейтральный минимальный

You are an AI assistant.
Answer the user's questions to the best of your ability.

Вы - ИИ-помощник.
Отвечайте на вопросы пользователя в меру своих возможностей.
"""


system_prompts = {
    "neutral": """You are a helpful, accurate, and concise AI assistant.
Follow the user's instructions carefully.
If something is unclear or missing, ask for clarification.
Do not make up facts.""",
    "programming_neutral": """You are a precise and reliable AI assistant.
Provide clear, structured, and technically correct answers.
If you are unsure, say so explicitly.
Do not invent details or assumptions.""",
    "minimal": """You are an AI assistant.
Answer the user's questions to the best of your ability."""
}



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
            {
                "role": "system",
                "content": system_prompts["neutral"]
            },
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





""""

Давай реализуем такую-же штуку как с output.log - там я перехватываю все сообщения которые вывожу в print.
Здесь давай создадим файл ChatGPT_history.log, в который будет писаться лог отправки и приёма сообщений

И тогда хранить не в памяти, а в этом файле, т.к. там может быть много текста, что бы оперативку не перегружать
Тогда нам будет проще отлаживать, и настраивать ограничения по кол-ву сообщений в истории и суммаризацию

Значит, при перезапуске программы пускай этот файл очищается, и в него будут добавляться данные при
отправке запроса, и при получении ответа

Давай хранить данные в формате 

{
    "chat_ случайный идентификатор, который создаётся для каждого нового чата":
    [
        {
            count_of_message: 1,
            request_msg: "Привет, мне нужно ...",
            response_msg: "Хорошо, вот ..."
            data_time: "18.12.2025 11:15",
            timestamp: 17__________,
        }
    ]
}

Тогда получается для каждого нового запроса будет создан новый объект chat_...
А если запрос был с историей, то используется и пишется ответ в тот чат, который мы используем

Например, пускай процедура вызова ChatGPT возвращает текстовый ответ, а также идентификатор чата,
к которому он привязался, что бы когда мы в следующий раз посылали запрос, то могли предоставить его
и он бы отправил историю этого чата

Также, я бы очень хотел иметь возможность обращаться к ответу как:
result_request = sendMessageToChatGPT_for_history("Какая самая высокая гора на земле?")
Что бы текстовый ответ был доступен по result_request.answer

И также сделай функцию инициализации пустого идентификатора чата, что бы например
в одном скрипте подключил код отправки запросов через ChatGPT, свреху файла создал этот идентификатор,
положил в переменную, и далее в этом файле отправлял запросы с ним, и все они бы
выполнялись в одной истории. А если надо, то напримеро просто получаю новый

Также давай хранить глобальный лог всей истории запросов и ответов нейросети. Т.е. после завершения программы будем 
записывать все сообщения из текущей сессии из ChatGPT_history.log в ChatGPT_history_global.log. 
Просто тогда в формате 

{
    {
        "chat_ случайный идентификатор, который создаётся для каждого нового чата":
        [
            {
            ...
    },
    {
    ...

Но будем удалять сессию, если она старше недели, что бы файл не становился огромным

Также сделай общий counter что бы отправлялось максимум 10 сообщений в истории
Если в истории больше сообщений - то выводи в лог предупреждение, доделаю это в будущем



"""

"""

Что подсказала нейросеть:

4️⃣ Предлагаемая API-форма (очень близко к твоему ТЗ)
🔹 Инициализация чата
chat_id = init_new_chat()


или

chat_id = init_new_chat(system_prompt="Ты опытный Python-разработчик")

🔹 Отправка сообщения
result = sendMessageToChatGPT_for_history(
    prompt="Какая самая высокая гора на земле?",
    chat_id=chat_id
)

print(result.answer)
print(result.chat_id)


✔ result.answer — ты этого прямо хотел
✔ chat_id сохраняется

🔹 Новый чат — просто новый id
chat_id = init_new_chat()

5️⃣ Как выглядит лог (чуть лучше)

Я бы чуть упростил структуру:

{
  "chat_id": "chat_abc123",
  "created_at": 1766030100,
  "system_prompt": "Ты опытный Python-разработчик",
  "messages": [
    {
      "index": 1,
      "role": "user",
      "content": "Какая самая высокая гора на земле?",
      "timestamp": 1766030123
    },
    {
      "index": 2,
      "role": "assistant",
      "content": "Самая высокая гора — Эверест",
      "timestamp": 1766030125
    }
  ]
}


Почему лучше:

один массив

легко сериализовать в OpenAI format

не нужно request_msg / response_msg

можно вставлять tool calls позже





2️⃣ Перед отправкой — projection / фильтрация

Отдельная функция:

def build_api_messages(chat_messages):
    api_messages = []

    for msg in chat_messages:
        api_messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    return api_messages

"""
