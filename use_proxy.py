import requests

DEFAULT_PROXY = "http://10.0.4.112:1020"

def request_for_proxy(url: str, proxy: str = DEFAULT_PROXY, timeout: int = 10) -> str:
    proxies = {
        "http": proxy,
        "https": proxy,
    }
    resp = requests.get(url, proxies=proxies, timeout=timeout)
    resp.raise_for_status()
    return resp.text


print("IP через прокси:", request_for_proxy("https://api.ipify.org"))