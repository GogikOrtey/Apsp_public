# from addedFunc import sendMessageToYandexGPT
from addedFunc import clearAnswerCode
from YandexGPT import *

# Обозначения переменных (буду сокращать для удобства):
# [описание запроса]_p1 = [описание запроса] prompt 1
# a_test_p1 = answer test prompt 1

# test_p1 = "Напиши код сортировки пузырьком на питоне"
# test_p1 = "Какой сейчас год и число?"
# test_p1 = "Почему когда я используя YandexGPT через api, ответы отличаются от тех, что я вижу, используя её через web-интерфейс?"
test_p1 = """
Есть такой код на JS: 
let totalItems = $("h2")?.text()?.trim()
Однако он извлекает "По вашему запросу найдено 575 результатов"
А должен извлекать: "575"
Измени исходный код, что бы он делал это.
"""
# a_test_p1 = sendMessageToYandexGPT(test_p1)
a_test_p1 = send_message_to_AI_agent(test_p1)
# a_test_p1 = sendMessageToYandexGPT(prompt = test_p1, temperature = 0, maxTokens = 300)
# print("Ответ от YandexGPT:")
# print(answer)

# print(clearAnswerCode(a_test_p1))


