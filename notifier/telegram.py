import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


def send_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }, timeout=10)
    response.raise_for_status()
    return True
