# antre/model.py

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("Deepseek")
API_URL = "https://api.deepseek.com/chat/completions"

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}


def call_model(messages, tools=None):
    data = {
        "model": "deepseek-v4-flash",
        "messages": messages,
        "stream": False
    }

    if tools:
        data["tools"] = tools
        data["tool_choice"] = "auto"

    response = requests.post(
        API_URL,
        headers=HEADERS,
        json=data,
        timeout=60
    )

    response.raise_for_status()

    return response.json()["choices"][0]["message"]