import os
from dotenv import load_dotenv
from google import genai

print(f"Запуск нейросети Gemini")

# Загружаем переменные окружения из .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Explain how AI works in a few words",
)

print(response.text)