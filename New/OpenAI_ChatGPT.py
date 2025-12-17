from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY")
if not api_key:
    raise RuntimeError(
        "OpenAI API key not found. Add OPENAI_API_KEY to your .env file"
    )

client = OpenAI(
    api_key=api_key
)

# Простой вариант использования API
response = client.responses.create(
    model="gpt-4.1-mini",
    # input="Привет! Объясни, что такое reasoning-агенты простыми словами"
    input="Какой сейчас год?"
)

print(response.output_text)
