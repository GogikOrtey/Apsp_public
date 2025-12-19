import random
import requests

DEFAULT_PROXY_HOST = "http://10.0.4.112"
DEFAULT_PORT = 1020
MIN_PORT = 1000
MAX_PORT = 1099

def request_for_proxy(
        url: str,
        *,
        port: int = DEFAULT_PORT,
        use_random_port: bool = True, # По умолчанию порт - рандомный
        proxy_host: str = DEFAULT_PROXY_HOST,
        headers: dict | None = None,
        timeout: int = 20,
        is_print = True
    ) -> str:

    if use_random_port:
        port = random.randint(MIN_PORT, MAX_PORT)
    if port < MIN_PORT or port > MAX_PORT:
        raise ValueError(f"Порт должен быть в диапазоне {MIN_PORT}-{MAX_PORT}")

    proxy = f"{proxy_host}:{port}"
    proxies = {
        "http": proxy,
        "https": proxy,
    }
    
    if is_print:
        print(f"🧢 Используем прокси: {proxy}")

    resp = requests.get(url, proxies=proxies, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


# print("IP через прокси:", request_for_proxy("https://api.ipify.org"))
# print("IP через прокси:", request_for_proxy("https://api.ipify.org", use_random_port = True))