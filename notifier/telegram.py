import re
import time

import requests
from requests import RequestException

from config import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN


def _build_url(token):
    return f"https://api.telegram.org/bot{token}/sendMessage"


def redact_telegram_secrets(value):
    if not value:
        return value

    redacted = str(value)
    if TELEGRAM_TOKEN:
        redacted = redacted.replace(TELEGRAM_TOKEN, "<telegram-token-redacted>")
    redacted = re.sub(r"/bot\d+:[A-Za-z0-9_-]+", "/bot<telegram-token-redacted>", redacted)
    return redacted


def send_message(text, retries=2, retry_delay=1.0, timeout=10):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = _build_url(TELEGRAM_TOKEN)
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    last_error = None

    for attempt in range(retries + 1):
        try:
            response = requests.post(url, data=payload, timeout=timeout)
            response.raise_for_status()
            return True
        except RequestException as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(retry_delay)

    raise RuntimeError(redact_telegram_secrets(last_error))
