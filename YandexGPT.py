# Подключение всех библиотек
from import_all_libraries import * 
from addedFunc import *

# Универсальная функция: send_message_to_AI_agent(str)

def send_message_to_AI_agent(prompt: str, no_hint = False):
    end_hint = """
Обязательные правила:
— Используй только опциональную цепочку ?. и не используй просто .
— Если должен быть доступ к элементу массива — используй только ?.at(i) вместо индексного обращения
— Никаких комментариев, пояснений, вариантов и текста вокруг в результате выдай только финальную 
строку или фрагмент кода.
    """

    if no_hint == False:
        prompt = prompt + end_hint
    result = sendMessageToYandexGPT(prompt)
    return result.replace("`", "").strip()

# Отправляет запрос к YandexGPT и возвращает текстовый ответ модели.
def sendMessageToYandexGPT(prompt: str, isSmartModel: bool = False, isPrint: bool = True, temperature = 0.8, maxTokens = 1024) -> str:
    print("Посылаю запрос к YandexGPT:")

    if isSmartModel:
        model = "yandexgpt"
        print("🧠 Используем умную модель")
        # model = "yandexgpt-pro" # Не работает
    else:
        model = "yandexgpt-lite" # Используется по умолчанию

    if isPrint:
            print(f"\n💫 PROMPT:\n{prompt}\n")

    load_dotenv()  # Загружаем .env с токеном API

    api_key = os.getenv("API_KEY")
    folder_id = "b1gomnf0uf3ims6eha2v"

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "modelUri": f"gpt://{folder_id}/{model}/latest",
        "completionOptions": {
            "stream": False,
            "temperature": temperature, #0.6,
            "maxTokens": maxTokens, #300

            # Добавьте параметр разнообразия
            "topP": 0.9,         
            "frequencyPenalty": 0.2,
            "presencePenalty": 0.2
        },
        "messages": [
            # {"role": "system", "text": "Ты — умный и дружелюбный помощник, отвечай подробно и естественно."},
            {"role": "user", "text": prompt}
        ]
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.ok:
        result = response.json()
        result_text = result["result"]["alternatives"][0]["message"]["text"]
        # print_result_text = formatted_json_prompt_and_answer(prompt, result_text)
        # if(isPrint): print("\n" + print_result_text + "\n") 
        # Потом можно будет вывести в словарь вместе с ответом
        if isPrint:
            # print(f"\n💫 PROMPT:\n{prompt}\n\n💬 AI ANSWER:\n{result_text}\n")
            print(f"\n💬 AI ANSWER:\n{result_text}\n")
        return result_text
    else:
        raise Exception(f"Ошибка {response.status_code}: {response.text}")
    
def formatted_json_prompt_and_answer(prompt, answer):
    data = {
        "prompt": prompt,
        "answer": answer
    }
    # И наверное надо будет добавлять что-то типо кода, или порядкового номера запроса. Но это позже
    return json.dumps(data, ensure_ascii=False, indent=4)
